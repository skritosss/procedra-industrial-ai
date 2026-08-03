import hashlib
import re

from app.schemas.instruction import (
    EvidenceClaim,
    EvidenceProvenance,
    EvidenceSourceType,
    InstructionRequest,
    InstructionResponse,
    RetrievedSource,
    SafetyFinding,
    WorkInstruction,
)


_HAZARDOUS_PATTERNS = (
    r"(?:отключить|обойти|деактивировать|снять)\s+(?:защит\w*|блокиров\w*|огражден\w*)",
    r"(?:disable|bypass|remove)\s+(?:the\s+)?(?:guard|interlock|protection)",
    r"(?:открыть|открывать)\s+(?:газ\w*\s+)?(?:клапан|вентиль|подачу газа)",
    r"(?:open)\s+(?:the\s+)?(?:gas\s+)?(?:valve|supply)",
    r"(?:отключить|деактивировать)\s+(?:сигнализац\w*|аварийн\w*\s+сигнал\w*)",
    r"(?:disable|deactivate)\s+(?:the\s+)?(?:alarm|emergency signal)",
    r"(?:помощник|работник|оператор|человек)\w*[^.!?]{0,60}(?:в опасн\w* зон\w*|в зоне движения)",
    r"(?:helper|worker|operator|person)[^.!?]{0,60}(?:danger zone|moving zone)",
)

_OVERRIDE_PATTERNS = (
    r"(?:скрыть|скрой|не показывай|не указывай)[^.!?]{0,50}(?:неопредел|сомнен|риск|провер)",
    r"(?:игнорировать|игнорируй|пропустить)[^.!?]{0,50}(?:провер|согласован|ревью|правил)",
    r"(?:считать|считай|пометить|пометь)[^.!?]{0,40}(?:подтвержден|безопасн)",
    r"(?:hide|omit|do not show)[^.!?]{0,50}(?:uncertainty|risk|review)",
    r"(?:ignore|skip)[^.!?]{0,50}(?:review|validation|rules)",
    r"(?:mark|treat)[^.!?]{0,40}(?:confirmed|safe)",
)

_NUMERIC_PATTERN = re.compile(
    r"\b\d+(?:[,.]\d+)?\s*(?:мм|см|мкм|кг|нм|об/мин|rpm|бар|bar|мпа|mpa|кпа|kpa|°\s*c|°c|градус\w*|сек\w*|мин\w*|час\w*)\b",
    re.IGNORECASE,
)


def analyze_untrusted_context(context: str | None) -> list[SafetyFinding]:
    if not context:
        return []

    compact = " ".join(context.split())
    lowered = compact.casefold().replace("ё", "е")
    findings: list[SafetyFinding] = []

    hazardous_match = _first_actionable_match(lowered, _HAZARDOUS_PATTERNS)
    if hazardous_match:
        findings.append(
            SafetyFinding(
                code="hazardous_action",
                severity="critical",
                message=(
                    "Непроверенный контекст содержит потенциально опасное действие; "
                    "его нельзя переносить в рабочую инструкцию без отклонения и экспертной проверки."
                ),
                evidence_excerpt=_excerpt(compact, hazardous_match.start(), hazardous_match.end()),
            )
        )

    contradiction_excerpt = _contradiction_excerpt(compact, lowered)
    if contradiction_excerpt:
        findings.append(
            SafetyFinding(
                code="contradictory_context",
                severity="critical",
                message=(
                    "Во входном контексте обнаружены взаимоисключающие состояния; "
                    "применение заблокировано до устранения противоречия."
                ),
                evidence_excerpt=contradiction_excerpt,
            )
        )

    numeric_match = _NUMERIC_PATTERN.search(compact)
    if numeric_match:
        findings.append(
            SafetyFinding(
                code="unsupported_numeric_claim",
                severity="high",
                message=(
                    "Точный числовой параметр получен из непроверенного контекста и должен быть "
                    "сверен с утвержденной локальной документацией."
                ),
                evidence_excerpt=_excerpt(compact, numeric_match.start(), numeric_match.end()),
            )
        )

    override_match = _first_actionable_match(lowered, _OVERRIDE_PATTERNS)
    if override_match:
        findings.append(
            SafetyFinding(
                code="instruction_override",
                severity="critical",
                message=(
                    "Контекст пытается скрыть неопределенность или обойти проверку; "
                    "такая инструкция не может получить safety-ready статус."
                ),
                evidence_excerpt=_excerpt(compact, override_match.start(), override_match.end()),
            )
        )

    return findings


def enforce_provenance_and_safety(
    instruction: WorkInstruction,
    request: InstructionRequest,
) -> WorkInstruction:
    guarded = instruction.model_copy(deep=True)
    guarded.workflow.status = "ai_draft"
    guarded.workflow.status_label = "AI-черновик"
    guarded.observed_facts = [_mark_claim_unverified(item) for item in guarded.observed_facts]
    guarded.evidence_claims = _build_evidence_claims(guarded.observed_facts)

    findings = analyze_untrusted_context(request.technical_context)
    for finding in findings:
        _append_unique(guarded.workflow.approval_blockers, f"Safety blocker [{finding.code}]: {finding.message}")
        _append_unique(guarded.local_verification_required, finding.message)
    return guarded


def link_evidence_claims_to_sources(
    instruction: WorkInstruction,
    sources: list[RetrievedSource],
) -> WorkInstruction:
    linked = instruction.model_copy(deep=True)
    for claim in linked.evidence_claims:
        best_source = _best_matching_source(claim.text, sources)
        if best_source is None:
            continue
        claim.provenance = "retrieved_unverified"
        claim.source_type = "retrieved_source"
        claim.source_id = best_source.source_id
        claim.claim_id = _claim_id(claim.provenance, claim.source_id, claim.text)
    return linked


def strip_client_claim_validations(payload: InstructionResponse) -> InstructionResponse:
    sanitized = payload.model_copy(deep=True)
    for claim in sanitized.instruction.evidence_claims:
        if claim.source_type == "retrieved_source":
            claim.provenance = "retrieved_unverified"
        elif claim.source_type == "model_output":
            claim.provenance = "model_inference"
        else:
            claim.provenance = "user_claim"
        claim.validation_status = "unverified"
        claim.requires_local_verification = True
        claim.validation_record = None
        claim.claim_id = _claim_id(claim.provenance, claim.source_id, claim.text)
    return sanitized


def _build_evidence_claims(observed_facts: list[str]) -> list[EvidenceClaim]:
    claims: list[EvidenceClaim] = []
    for item in observed_facts:
        lowered = item.casefold()
        if any(
            marker in lowered
            for marker in [
                "входных данных",
                "запрос",
                "указан",
                "непроверенн",
                "контекст",
                "тип инструкции",
                "уровень пользователя",
                "отраслевой профиль",
            ]
        ):
            provenance: EvidenceProvenance = "user_claim"
            source_id = "request"
            source_type: EvidenceSourceType = "user_input"
        else:
            provenance = "model_inference"
            source_id = "generation:postprocess"
            source_type = "model_output"
        claims.append(
            EvidenceClaim(
                claim_id=_claim_id(provenance, source_id, item),
                text=item,
                provenance=provenance,
                source_id=source_id,
                source_type=source_type,
                validation_status="unverified",
                requires_local_verification=True,
            )
        )
    return claims[:20]


def _best_matching_source(
    claim_text: str,
    sources: list[RetrievedSource],
) -> RetrievedSource | None:
    claim_words = _meaningful_words(claim_text)
    if not claim_words:
        return None
    ranked: list[tuple[float, RetrievedSource]] = []
    for source in sources:
        source_words = _meaningful_words(source.excerpt)
        if not source_words:
            continue
        overlap = len(claim_words & source_words) / len(claim_words)
        ranked.append((overlap, source))
    if not ranked:
        return None
    score, source = max(ranked, key=lambda item: item[0])
    return source if score >= 0.2 else None


def _meaningful_words(value: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-zа-я0-9]+", value.casefold().replace("ё", "е"))
        if len(word) >= 5
        and word
        not in {
            "непроверенное",
            "утверждение",
            "входного",
            "контекста",
            "указано",
            "данных",
        }
    }


def _claim_id(provenance: str, source_id: str | None, text: str) -> str:
    canonical = "|".join(
        [
            provenance,
            source_id or "none",
            " ".join(text.casefold().split()),
        ]
    )
    return f"claim_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]}"


def _mark_claim_unverified(value: str) -> str:
    cleaned = re.sub(
        r"^(?:подтвержденн(?:ый|ая|ое|ые)?\s+контекст(?:\s+запроса/источников)?|confirmed context)\s*:\s*",
        "",
        value.strip(),
        flags=re.IGNORECASE,
    )
    if cleaned != value.strip() or "подтвержденн" in value.casefold() or "confirmed" in value.casefold():
        cleaned = re.sub(r"\bподтвержденн\w*\b", "непроверенный", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bconfirmed\b", "unverified", cleaned, flags=re.IGNORECASE)
    if cleaned.casefold().startswith("непроверенн"):
        return cleaned
    if "контекст" in value.casefold() or cleaned != value.strip():
        return f"Непроверенное утверждение из входного контекста: {cleaned}"
    return cleaned


_ABSENCE_MARKERS = re.compile(
    r"\b(?:нет|без|отсутств\w*|не\s+должн\w*|не\s+допуска\w*|исключ\w*|"
    r"no|not|without|free of|absence)\b",
    re.IGNORECASE,
)


def _first_actionable_match(text: str, patterns: tuple[str, ...]) -> re.Match[str] | None:
    """Find a hazardous instruction, ignoring sentences that forbid it.

    Checking only the words immediately before the match caught "не отключать
    блокировку" but not the far more common industrial phrasing, where the
    negation follows: "убедиться, что в зоне движения нет людей". That sentence
    demands the opposite of a hazard, and flagging it fired a critical blocker on
    the project's own curated safety texts — every occupational-safety draft
    generated with public sources came out critical. A detector that fires on
    correct safety writing teaches its users to ignore it.

    So the whole sentence around the match is inspected: a negation before it, or
    a statement of absence anywhere in it, means the text is describing a
    requirement rather than ordering a dangerous act.
    """
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            prefix = text[max(0, match.start() - 28) : match.start()]
            if re.search(r"(?:не|нельзя|запрещ\w*|do not|must not|never)\s*$", prefix):
                continue
            if _ABSENCE_MARKERS.search(_sentence_around(text, match.start(), match.end())):
                continue
            return match
    return None


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(
        (text.rfind(mark, 0, start) for mark in (".", "!", "?", ";")),
        default=-1,
    )
    right_candidates = [position for position in (text.find(mark, end) for mark in (".", "!", "?", ";")) if position != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1 : right]


def _contradiction_excerpt(original: str, lowered: str) -> str | None:
    pairs = (
        (("огражден", "guard"), ("закрыт", "closed"), ("открыт", "open")),
        (("блокиров", "interlock"), ("включен", "enabled"), ("отключен", "disabled")),
        (("клапан", "valve"), ("закрыт", "closed"), ("открыт", "open")),
    )
    for subjects, states_a, states_b in pairs:
        subject_pattern = "(?:" + "|".join(subjects) + ")"
        state_a_pattern = "(?:" + "|".join(states_a) + ")"
        state_b_pattern = "(?:" + "|".join(states_b) + ")"
        direct_patterns = (
            rf"{subject_pattern}[^.!?;]{{0,50}}{state_a_pattern}\s+(?:и|and)\s+(?:одновременно\s+)?{state_b_pattern}",
            rf"{subject_pattern}[^.!?;]{{0,50}}{state_b_pattern}\s+(?:и|and)\s+(?:одновременно\s+)?{state_a_pattern}",
        )
        if any(re.search(pattern, lowered) for pattern in direct_patterns):
            return original[:300]
        clauses = [
            clause.strip()
            for clause in re.split(r"[.!?;,]+|\b(?:and|а|но)\b", lowered)
            if clause.strip()
        ]
        subject_clauses = [
            clause for clause in clauses if any(subject in clause for subject in subjects)
        ]
        has_state_a = any(
            any(state in clause for state in states_a) for clause in subject_clauses
        )
        has_state_b = any(
            any(state in clause for state in states_b) for clause in subject_clauses
        )
        if has_state_a and has_state_b:
            return original[:300]
    return None


def _excerpt(text: str, start: int, end: int, radius: int = 90) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)][:300]


def _append_unique(target: list[str], value: str) -> None:
    if value.casefold() not in {item.casefold() for item in target}:
        target.append(value)
