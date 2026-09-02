import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


from app.core.settings import get_settings
from app.providers.errors import ProviderEgressBlockedError, ProviderError, ProviderNotConfiguredError
from app.providers.perimeter import report_blocked, report_degraded
from app.providers.registry import embedding_provider
from app.retrieval.public_sources import retrieve_public_sources
from app.schemas.instruction import ContextGenerationRequest, RetrievedSource


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_BASE = PROJECT_ROOT / "examples" / "knowledge_base"
UPLOADED_KNOWLEDGE_BASE = PROJECT_ROOT / "uploads" / "documents"
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
LOCAL_EMBEDDING_DIMS = 256
SEMANTIC_WEIGHT = 0.7
LEXICAL_WEIGHT = 0.3
MAX_INDEX_FILE_BYTES = 1_000_000
MAX_EMBEDDING_TEXT_CHARS = 6_000


@dataclass(frozen=True)
class DocumentChunk:
    source_id: str
    title: str
    path: Path
    chunk_index: int
    text: str
    tokens: set[str]
    local_embedding: tuple[float, ...]


def retrieve_sources(
    request: ContextGenerationRequest,
    knowledge_base: Path = DEFAULT_KNOWLEDGE_BASE,
    uploaded_knowledge_base: Path | None = None,
    uploaded_document_ids: frozenset[str] | None = None,
) -> list[RetrievedSource]:
    local_sources = _retrieve_local_sources(request, knowledge_base)
    uploaded_sources = _retrieve_local_sources(
        request,
        uploaded_knowledge_base or UPLOADED_KNOWLEDGE_BASE,
        authority="Загруженные документы пользователя",
        document_type="Загруженный документ предприятия",
        allowed_source_ids=uploaded_document_ids,
    )
    public_sources = _maybe_retrieve_public_sources(request)
    return _merge_retrieved_sources(local_sources, public_sources, request.max_sources, uploaded_sources)


def _retrieve_local_sources(
    request: ContextGenerationRequest,
    knowledge_base: Path = DEFAULT_KNOWLEDGE_BASE,
    authority: str = "Локальная база проекта",
    document_type: str = "Локальный технический документ",
    allowed_source_ids: frozenset[str] | None = None,
) -> list[RetrievedSource]:
    chunks = _load_chunks(str(knowledge_base), _knowledge_base_signature(knowledge_base))
    if allowed_source_ids is not None:
        chunks = tuple(chunk for chunk in chunks if chunk.source_id in allowed_source_ids)
    if not chunks:
        return []
    query = _request_query(request)
    query_tokens = _tokenize(query)
    if not query_tokens and not query.strip():
        return []
    query_embedding, chunk_embeddings, embedding_mode = _embedding_bundle(query, chunks)
    source_hint = _source_hint(request)
    scored = [
        (
            chunk,
            _hybrid_score(
                query_tokens=query_tokens,
                query_embedding=query_embedding,
                chunk=chunk,
                chunk_embedding=chunk_embeddings[_chunk_key(chunk)],
                all_chunks=chunks,
                embedding_mode=embedding_mode,
                source_hint=source_hint,
            ),
        )
        for chunk in chunks
    ]
    ranked = [
        (chunk, score)
        for chunk, score in sorted(scored, key=lambda item: item[1], reverse=True)
        if score > 0
    ][: request.max_sources]
    return [
        RetrievedSource(
            source_id=chunk.source_id,
            title=chunk.title,
            path=_source_path(chunk.path),
            chunk_index=chunk.chunk_index,
            score=round(score, 4),
            excerpt=_excerpt(chunk.text, query_tokens),
            source_type="local",
            influence_score=_influence_score(score),
            matched_terms=sorted(query_tokens & chunk.tokens)[:8],
            authority=authority,
            document_type=document_type,
            applicable_profiles=[request.industry_profile],
            contribution_reason=_local_contribution_reason(chunk, query_tokens, source_hint),
        )
        for chunk, score in ranked
    ]


def _maybe_retrieve_public_sources(request: ContextGenerationRequest) -> list[RetrievedSource]:
    settings = get_settings()
    if not getattr(settings, "public_sources_enabled", True):
        return []
    public_limit = min(max(int(getattr(settings, "public_sources_max_results", 15)), 0), request.max_sources)
    return retrieve_public_sources(request, public_limit)


def _merge_retrieved_sources(
    local_sources: list[RetrievedSource],
    public_sources: list[RetrievedSource],
    max_sources: int,
    uploaded_sources: list[RetrievedSource] | None = None,
) -> list[RetrievedSource]:
    if max_sources <= 0:
        return []
    uploaded_sources = uploaded_sources or []
    preferred_local_sources = [*uploaded_sources, *local_sources]
    if not public_sources:
        return preferred_local_sources[:max_sources]
    if not preferred_local_sources:
        return public_sources[:max_sources]

    local_reserve = min(len(preferred_local_sources), max(1, max_sources // 5))
    public_take = min(len(public_sources), max_sources - local_reserve)
    local_take = min(len(preferred_local_sources), max(0, max_sources - public_take))
    combined = [*public_sources[:public_take], *preferred_local_sources[:local_take]]
    seen = set()
    deduped = []
    for source in combined:
        key = (source.source_id, source.path, source.chunk_index)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
        if len(deduped) >= max_sources:
            break
    return deduped


def build_context_from_sources(sources: list[RetrievedSource]) -> str:
    if not sources:
        return ""
    parts = []
    for source in sources:
        profiles = ", ".join(source.applicable_profiles) if source.applicable_profiles else "не указаны"
        parts.append(
            (
                f"[{source.source_id} #{source.chunk_index} | type={source.source_type} | score={source.score} | "
                f"influence={source.influence_score}] {source.title}\n"
                f"Источник: {source.url or source.path}\n"
                f"Тип документа: {source.document_type or 'не указан'}\n"
                f"Орган/площадка: {source.authority or 'не указано'}\n"
                f"Профили применимости: {profiles}\n"
                f"Почему выбран: {source.contribution_reason or 'причина не указана'}\n"
                f"{source.excerpt}"
            )
        )
    return "\n\n".join(parts)


@lru_cache(maxsize=8)
def _load_chunks(knowledge_base_path: str, knowledge_base_signature: tuple[tuple[str, int, int], ...]) -> tuple[DocumentChunk, ...]:
    knowledge_base = Path(knowledge_base_path)
    if not knowledge_base.exists():
        return ()
    chunks: list[DocumentChunk] = []
    for path in _knowledge_base_files(knowledge_base):
        if path.stat().st_size > MAX_INDEX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        title = _extract_title(text, path)
        for index, chunk_text in enumerate(_chunk_text(text), start=1):
            tokens = _tokenize(chunk_text)
            chunks.append(
                DocumentChunk(
                    source_id=path.stem,
                    title=title,
                    path=path,
                    chunk_index=index,
                    text=chunk_text,
                    tokens=tokens,
                    local_embedding=_local_embedding(chunk_text),
                )
            )
    return tuple(chunks)


def _chunk_text(text: str, max_chars: int = 900) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def _knowledge_base_files(knowledge_base: Path) -> list[Path]:
    return sorted(
        path
        for path in [*knowledge_base.glob("*.md"), *knowledge_base.glob("*.txt")]
        if path.is_file() and not path.is_symlink()
    )


def _knowledge_base_signature(knowledge_base: Path) -> tuple[tuple[str, int, int], ...]:
    if not knowledge_base.exists():
        return ()
    signature = []
    for path in _knowledge_base_files(knowledge_base):
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((str(path), stat.st_size, stat.st_mtime_ns))
    return tuple(signature)


def _extract_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or path.stem
        if stripped:
            return stripped[:80]
    return path.stem


def _request_query(request: ContextGenerationRequest) -> str:
    return " ".join(
        part
        for part in [
            request.task,
            request.operation_name or "",
            request.industry_profile,
            request.department or "",
            request.equipment or "",
            request.technical_context or "",
            request.instruction_type,
        ]
        if part
    )


def _score_chunk(query_tokens: set[str], chunk: DocumentChunk, all_chunks: Sequence[DocumentChunk]) -> float:
    overlap = query_tokens & chunk.tokens
    if not overlap:
        return 0.0
    score = 0.0
    total_chunks = len(all_chunks)
    for token in overlap:
        document_frequency = sum(1 for candidate in all_chunks if token in candidate.tokens)
        idf = math.log((1 + total_chunks) / (1 + document_frequency)) + 1
        score += idf
    return score / math.sqrt(max(len(chunk.tokens), 1))


def _hybrid_score(
    query_tokens: set[str],
    query_embedding: tuple[float, ...],
    chunk: DocumentChunk,
    chunk_embedding: tuple[float, ...],
    all_chunks: tuple[DocumentChunk, ...],
    embedding_mode: str,
    source_hint: str | None,
) -> float:
    lexical_score = _score_chunk(query_tokens, chunk, all_chunks)
    lexical_normalized = lexical_score / (1 + lexical_score)
    semantic_score = max(0.0, _cosine_similarity(query_embedding, chunk_embedding))
    if lexical_score <= 0 and semantic_score < _semantic_threshold(embedding_mode):
        return 0.0
    hint_boost = 0.25 if source_hint and chunk.source_id == source_hint else 0.0
    return SEMANTIC_WEIGHT * semantic_score + LEXICAL_WEIGHT * lexical_normalized + hint_boost


def _embedding_bundle(
    query: str,
    chunks: tuple[DocumentChunk, ...],
) -> tuple[tuple[float, ...], dict[tuple[str, int], tuple[float, ...]], str]:
    settings = get_settings()
    if getattr(settings, "openai_enabled", False) and getattr(settings, "openai_api_key", None):
        try:
            texts = (_embedding_input(query), *(_embedding_input(chunk.text) for chunk in chunks))
            embeddings = _model_embeddings(texts)
            return (
                embeddings[0],
                {_chunk_key(chunk): embeddings[index + 1] for index, chunk in enumerate(chunks)},
                "model",
            )
        except ProviderEgressBlockedError as error:
            # Caught ahead of ProviderError so the refusal is recorded rather
            # than absorbed as an ordinary embedding failure.
            report_blocked(error, "embedding")
        except (ProviderError, ValueError, IndexError) as error:
            # AttributeError used to be caught here too. It is not a provider
            # fault but a mistake in this code — a renamed field, a None where an
            # object was expected — and swallowing it turned a bug into quietly
            # worse retrieval. It now propagates.
            report_degraded(error, "embedding")
    return (
        _local_embedding(query),
        {_chunk_key(chunk): chunk.local_embedding for chunk in chunks},
        "deterministic",
    )


def _model_embeddings(texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
    """Ask the configured provider for vectors.

    Built through the registry rather than directly, so a deployment that points
    `LLM_BASE_URL` at its own endpoint gets embeddings from there too. Building
    the provider here by hand quietly sent them to the vendor default while
    generation went elsewhere — the kind of split that is invisible until
    retrieval quality drops in a closed perimeter.
    """
    provider = embedding_provider()
    if provider is None:
        raise ProviderNotConfiguredError("registry", "no embedding provider configured")
    return provider.embed(texts)


def _local_embedding(text: str) -> tuple[float, ...]:
    vector = [0.0] * LOCAL_EMBEDDING_DIMS
    for feature, weight in _semantic_features(text):
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=6).digest()
        bucket = int.from_bytes(digest[:4], "big") % LOCAL_EMBEDDING_DIMS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


def _semantic_features(text: str) -> list[tuple[str, float]]:
    normalized_tokens = _token_sequence(text)
    token_counts = Counter(normalized_tokens)
    features: list[tuple[str, float]] = [
        (f"tok:{token}", min(3.0, math.sqrt(count))) for token, count in token_counts.items()
    ]
    compact = " ".join(normalized_tokens)
    for size, weight in ((3, 0.35), (4, 0.25)):
        for index in range(0, max(len(compact) - size + 1, 0)):
            gram = compact[index : index + size]
            if " " not in gram:
                features.append((f"gram:{gram}", weight))
    return features


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(left_value * right_value for left_value, right_value in zip(left, right)) / (left_norm * right_norm)


def _semantic_threshold(embedding_mode: str) -> float:
    return 0.18 if embedding_mode == "deterministic" else 0.1


def _chunk_key(chunk: DocumentChunk) -> tuple[str, int]:
    return (str(chunk.path), chunk.chunk_index)


def _source_hint(request: ContextGenerationRequest) -> str | None:
    hints = {
        "workplace_preparation": "workplace_preparation",
        "equipment_startup": "equipment_startup",
        "equipment_shutdown": "shift_handover",
    }
    return hints.get(request.instruction_type)


def _influence_score(score: float) -> float:
    if score <= 0:
        return 0.0
    return round(min(1.0, score / (score + 0.35)), 3)


def _local_contribution_reason(chunk: DocumentChunk, query_tokens: set[str], source_hint: str | None) -> str:
    reasons = []
    matched_terms = sorted(query_tokens & chunk.tokens)[:5]
    if matched_terms:
        reasons.append(f"совпали термины локальной базы: {', '.join(matched_terms)}")
    if source_hint and chunk.source_id == source_hint:
        reasons.append("документ соответствует типу инструкции")
    if not reasons:
        reasons.append("источник выбран по семантической близости к запросу")
    return f"Локальный источник выбран, потому что {', '.join(reasons)}."


def _source_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return path.name


def _tokenize(text: str) -> set[str]:
    return set(_token_sequence(text))


def _token_sequence(text: str) -> list[str]:
    stopwords = {
        "и",
        "в",
        "на",
        "по",
        "для",
        "или",
        "при",
        "что",
        "после",
        "перед",
        "должен",
        "должна",
        "необходимо",
        "оператор",
        "оператора",
        "оборудование",
        "оборудования",
        "оборудованию",
        "рабочее",
        "рабочего",
        "рабочем",
        "место",
        "места",
        "месте",
    }
    normalized_stopwords = {_normalize_token(token) for token in stopwords}
    tokens = []
    for token in TOKEN_RE.findall(text):
        normalized = _normalize_token(token)
        if len(normalized) >= 4 and normalized not in normalized_stopwords:
            tokens.append(normalized)
    return tokens


def _embedding_input(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:MAX_EMBEDDING_TEXT_CHARS]


def _normalize_token(token: str) -> str:
    lowered = token.lower().replace("ё", "е")
    replacements = {
        "остановить": "останов",
        "остановка": "останов",
        "останавливает": "останов",
        "передать": "передач",
        "передача": "передач",
        "передается": "передач",
        "передачи": "передач",
        "смену": "смен",
        "смены": "смен",
        "смена": "смен",
        "запустить": "запуск",
        "запуска": "запуск",
        "запуск": "запуск",
        "подготовить": "подготовк",
        "подготовка": "подготовк",
        "подготовки": "подготовк",
    }
    if lowered in replacements:
        return replacements[lowered]
    endings = (
        "иями",
        "ями",
        "ами",
        "ого",
        "ему",
        "ыми",
        "ими",
        "ить",
        "ать",
        "ией",
        "ия",
        "ий",
        "ый",
        "ой",
        "ые",
        "ая",
        "ое",
        "ов",
        "ев",
        "ам",
        "ям",
        "ах",
        "ях",
        "ом",
        "ем",
        "ою",
        "ею",
        "а",
        "я",
        "ы",
        "и",
        "у",
        "ю",
        "е",
    )
    for ending in endings:
        if lowered.endswith(ending) and len(lowered) - len(ending) >= 4:
            return lowered[: -len(ending)]
    return lowered


def _excerpt(text: str, query_tokens: set[str] | None = None, max_chars: int = 520) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    focused = _focused_excerpt(compact, query_tokens or set(), max_chars)
    if focused:
        return focused
    return compact[: max_chars - 1].rstrip() + "..."


def _focused_excerpt(text: str, query_tokens: set[str], max_chars: int) -> str:
    if not query_tokens:
        return ""
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    if not sentences:
        return ""
    scored = []
    for index, sentence in enumerate(sentences):
        sentence_tokens = set(_token_sequence(sentence))
        overlap = len(query_tokens & sentence_tokens)
        scored.append((overlap, -index, index))
    best_overlap, _, best_index = max(scored)
    if best_overlap <= 0:
        return ""
    selected = [sentences[best_index]]
    cursor = best_index - 1
    while cursor >= 0 and len(" ".join([sentences[cursor], *selected])) <= max_chars:
        selected.insert(0, sentences[cursor])
        cursor -= 1
    cursor = best_index + 1
    while cursor < len(sentences) and len(" ".join([*selected, sentences[cursor]])) <= max_chars:
        selected.append(sentences[cursor])
        cursor += 1
    result = " ".join(selected)
    if len(result) <= max_chars:
        return result
    return result[: max_chars - 1].rstrip() + "..."
