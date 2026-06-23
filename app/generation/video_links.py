import re
from collections.abc import Iterable

from app.schemas.instruction import StepFrameLink, WorkInstruction
from app.schemas.video import FrameAnalysis, Keyframe, VideoSegment


_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
_SAFE_LOCAL_IMAGE_URL_RE = re.compile(r"^/generated/keyframes/[A-Za-z0-9_./-]+$")
_STOPWORDS = {
    "и",
    "в",
    "во",
    "на",
    "с",
    "со",
    "к",
    "ко",
    "от",
    "до",
    "для",
    "по",
    "при",
    "перед",
    "после",
    "или",
    "а",
    "но",
    "как",
    "что",
    "это",
    "не",
    "без",
    "над",
    "под",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "with",
    "оператор",
    "оператора",
    "оператору",
    "оператором",
    "действие",
    "действия",
    "действий",
    "результат",
    "результата",
    "проверить",
    "проверка",
    "проверки",
    "состояние",
    "состояния",
    "оборудование",
    "оборудования",
    "рабочее",
    "рабочего",
    "место",
    "места",
}

_MIN_CONFIDENT_SCORE = 2


def link_steps_to_frames(
    instruction: WorkInstruction,
    frame_analyses: list[FrameAnalysis],
    keyframes: list[Keyframe],
    video_segments: list[VideoSegment] | None = None,
) -> list[StepFrameLink]:
    """Build deterministic links between instruction steps and video frames."""
    if not instruction.steps or not keyframes:
        return []

    frames = _merge_frame_data(frame_analyses, keyframes, video_segments or [])
    if not frames:
        return []

    frames = sorted(frames, key=lambda frame: (frame["timestamp_seconds"], frame["frame_index"]))
    links: list[StepFrameLink] = []
    used_frame_indices: set[int] = set()
    for index, step in enumerate(instruction.steps):
        step_tokens = _tokens(
            [
                step.action,
                step.expected_result,
                step.safety_note,
                step.verification_method,
                *step.common_mistakes,
            ]
        )
        best_frame = None
        best_match = (-1.0, -1.0, 0.0)
        for frame in frames:
            semantic_score = _score_tokens(step_tokens, frame["tokens"])
            temporal_score = _temporal_score(index, len(instruction.steps), frame["position"], len(frames))
            reuse_penalty = 0.75 if frame["frame_index"] in used_frame_indices else 0.0
            combined_score = semantic_score + temporal_score - reuse_penalty
            match = (combined_score, float(semantic_score), temporal_score)
            if match > best_match:
                best_match = match
                best_frame = frame

        if best_frame is None:
            continue

        best_semantic_score = int(best_match[1])
        if best_semantic_score < _MIN_CONFIDENT_SCORE:
            best_frame = frames[_relative_index(index, len(instruction.steps), len(frames))]
            confidence = 0.2
            reason = "Прямая смысловая связь не найдена; кадр выбран по порядку выполнения операции."
        else:
            confidence = min(0.95, 0.35 + best_semantic_score / max(len(step_tokens), 1))
            reason = (
                "Кадр связан с шагом по совпадению действий, объектов или требований безопасности "
                "с учетом положения шага во времени операции."
            )
        used_frame_indices.add(best_frame["frame_index"])

        links.append(
            StepFrameLink(
                step_number=step.number,
                frame_index=best_frame["frame_index"],
                timestamp_seconds=best_frame["timestamp_seconds"],
                reason=reason,
                confidence=round(confidence, 2),
                image_url=_safe_image_url(best_frame["image_url"]),
                analysis_mode=best_frame["analysis_mode"],
            )
        )
    return links


def _merge_frame_data(
    frame_analyses: list[FrameAnalysis],
    keyframes: list[Keyframe],
    video_segments: list[VideoSegment],
) -> list[dict]:
    analyses_by_frame = {analysis.frame_index: analysis for analysis in frame_analyses}
    segment_text_by_frame = _segment_text_by_frame(video_segments)
    merged: list[dict] = []
    for keyframe in keyframes:
        position = len(merged)
        analysis = analyses_by_frame.get(keyframe.frame_index)
        text_parts: list[str] = []
        analysis_mode = None
        if analysis:
            analysis_mode = analysis.analysis_mode
            text_parts = [
                analysis.summary,
                *analysis.visible_equipment,
                *analysis.operator_actions,
                *analysis.safety_observations,
                *analysis.ppe_observations,
                *analysis.potential_hazards,
                *analysis.uncertainties,
            ]
        text_parts.extend(segment_text_by_frame.get(keyframe.frame_index, []))
        merged.append(
            {
                "frame_index": keyframe.frame_index,
                "timestamp_seconds": keyframe.timestamp_seconds,
                "image_url": keyframe.image_url,
                "analysis_mode": analysis_mode,
                "tokens": _tokens(text_parts),
                "position": position,
            }
        )
    return merged


def _segment_text_by_frame(video_segments: list[VideoSegment]) -> dict[int, list[str]]:
    result: dict[int, list[str]] = {}
    for segment in video_segments:
        text_parts = [
            segment.summary,
            *segment.dominant_actions,
            *segment.visible_equipment,
            *segment.safety_findings,
            *segment.uncertainties,
        ]
        for frame_index in segment.frame_indices:
            result.setdefault(frame_index, []).extend(text_parts)
    return result


def _tokens(values: Iterable[str | None]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        for token in _TOKEN_RE.findall(value.lower().replace("ё", "е")):
            if len(token) >= 3 and token not in _STOPWORDS:
                tokens.add(token)
                normalized = _normalize_token(token)
                if normalized and normalized not in _STOPWORDS:
                    tokens.add(normalized)
    return tokens


def _score_tokens(step_tokens: set[str], frame_tokens: set[str]) -> int:
    if not step_tokens or not frame_tokens:
        return 0
    return len(step_tokens & frame_tokens)


def _temporal_score(step_index: int, step_count: int, frame_position: int, frame_count: int) -> float:
    if step_count <= 1 or frame_count <= 1:
        return 0.0
    expected = step_index / (step_count - 1)
    actual = frame_position / (frame_count - 1)
    distance = abs(expected - actual)
    return max(0.0, 1.0 - distance)


def _normalize_token(token: str) -> str:
    for suffix in (
        "иями",
        "ями",
        "ами",
        "ого",
        "ему",
        "ыми",
        "ими",
        "ать",
        "ять",
        "ить",
        "ешь",
        "ает",
        "яет",
        "уют",
        "ют",
        "ый",
        "ий",
        "ой",
        "ая",
        "ое",
        "ые",
        "ых",
        "ам",
        "ям",
        "ом",
        "ем",
        "ах",
        "ях",
        "а",
        "я",
        "ы",
        "и",
        "е",
        "у",
    ):
        if len(token) - len(suffix) >= 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _safe_image_url(image_url: str | None) -> str | None:
    if not image_url:
        return None
    if ".." not in image_url and _SAFE_LOCAL_IMAGE_URL_RE.fullmatch(image_url):
        return image_url
    return None


def _relative_index(step_index: int, step_count: int, frame_count: int) -> int:
    if frame_count <= 1 or step_count <= 1:
        return 0
    return round(step_index * (frame_count - 1) / (step_count - 1))
