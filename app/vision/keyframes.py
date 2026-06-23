import html
import json
import re
import socket
from typing import Any, cast
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import cv2
import numpy as np

from app.core.settings import get_settings
from app.core.organization import LEGACY_ORGANIZATION_ID, organization_storage_path
from app.schemas.video import Keyframe, VideoKeyframeResponse
from app.vision.safe_egress import SafeYoutubeDL, VideoEgressPolicy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "uploads" / "videos"
KEYFRAME_DIR = PROJECT_ROOT / "generated" / "keyframes"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
CONTEXT_LIMIT = 6000
TRANSCRIPT_LIMIT = 5000
TRANSCRIPT_TRACK_MAX_BYTES = 1_000_000
VISUAL_QUALITY_HEIGHTS = {240, 360, 720, 1080}
MIN_KEYFRAME_DIFFERENCE = 4.0


@dataclass(frozen=True)
class KeyframeCandidate:
    frame_index: int
    frame: np.ndarray
    gray: np.ndarray
    timestamp_seconds: float
    scene_change: float
    sharpness: float
    brightness_score: float
    contrast_score: float
    score: float


def save_uploaded_video(
    filename: str,
    content: bytes,
    organization_id: str = LEGACY_ORGANIZATION_ID,
) -> tuple[str, Path]:
    max_bytes = get_settings().video_max_bytes
    if len(content) > max_bytes:
        raise ValueError(f"Video file is too large. Maximum size is {max_bytes // (1024 * 1024)} MB")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Unsupported video format")
    video_id = uuid.uuid4().hex
    upload_dir = organization_storage_path(UPLOAD_DIR, organization_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = upload_dir / f"{video_id}{suffix}"
    video_path.write_bytes(content)
    return video_id, video_path


def download_video_from_url(
    video_url: str,
    visual_quality: int | str = 720,
    organization_id: str = LEGACY_ORGANIZATION_ID,
) -> tuple[str, Path, dict[str, str]]:
    target_height = _normalize_visual_quality(visual_quality)
    policy = _video_egress_policy()
    policy.resolve(video_url)
    metadata = fetch_video_metadata(video_url, policy=policy)
    video_id = uuid.uuid4().hex
    upload_dir = organization_storage_path(UPLOAD_DIR, organization_id)
    output_template = str(upload_dir / f"{video_id}.%(ext)s")
    upload_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    max_bytes = settings.video_max_bytes
    options = {
        "format": _format_for_visual_quality(target_height),
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": max_bytes,
        "socket_timeout": settings.video_network_timeout_seconds,
        "continuedl": False,
        "noprogress": True,
        "hls_prefer_native": True,
    }
    try:
        with SafeYoutubeDL(cast(dict[str, Any], options), policy) as downloader:
            info = downloader.extract_info(video_url, download=False)
            info_dict = cast(dict[str, Any], info)
            _validate_download_info_egress(info_dict, policy)
            downloader.process_info(cast(Any, info_dict))
    except Exception as exc:
        _remove_download_candidates(video_id, organization_id)
        raise ValueError("Unable to download video from URL") from exc

    downloaded = _find_downloaded_video(video_id, organization_id)
    if downloaded is None:
        _remove_download_candidates(video_id, organization_id)
        raise ValueError("Downloaded video file was not found")
    if downloaded.stat().st_size > max_bytes:
        _remove_download_candidates(video_id, organization_id)
        raise ValueError(f"Downloaded video is too large. Maximum size is {max_bytes // (1024 * 1024)} MB")
    metadata["title"] = metadata.get("title") or str(info.get("title") or video_url)
    metadata["source_url"] = metadata.get("source_url") or str(info.get("webpage_url") or video_url)
    metadata["visual_quality"] = f"{target_height}p"
    return video_id, downloaded, metadata


def fetch_video_metadata(video_url: str, *, policy: VideoEgressPolicy | None = None) -> dict[str, str]:
    policy = policy or _video_egress_policy()
    policy.resolve(video_url)
    settings = get_settings()
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "noprogress": True,
        "socket_timeout": settings.video_network_timeout_seconds,
    }
    try:
        with SafeYoutubeDL(cast(dict[str, Any], options), policy) as downloader:
            info = downloader.extract_info(video_url, download=False)
    except Exception as exc:
        raise ValueError("Unable to read video metadata") from exc
    info_dict = cast(dict[str, Any], info)
    _reject_known_oversized_video(info_dict)

    metadata = {
        "title": str(info_dict.get("title") or video_url),
        "source_url": str(info_dict.get("webpage_url") or video_url),
        "description": _clean_text(str(info_dict.get("description") or ""))[:CONTEXT_LIMIT],
        "transcript": _extract_transcript(info_dict, policy=policy),
    }
    metadata["extracted_context"] = _build_extracted_context(metadata)
    return metadata


def _find_downloaded_video(video_id: str, organization_id: str = LEGACY_ORGANIZATION_ID) -> Path | None:
    upload_dir = organization_storage_path(UPLOAD_DIR, organization_id)
    candidates = sorted(upload_dir.glob(f"{video_id}.*"))
    for path in candidates:
        suffixes = [suffix.lower() for suffix in path.suffixes]
        if ".part" not in suffixes and path.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
            return path
    return None


def _remove_download_candidates(video_id: str, organization_id: str = LEGACY_ORGANIZATION_ID) -> None:
    upload_dir = organization_storage_path(UPLOAD_DIR, organization_id)
    for path in upload_dir.glob(f"{video_id}.*"):
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)


def _validate_public_video_url(video_url: str) -> None:
    _video_egress_policy().resolve(video_url)


def _video_egress_policy() -> VideoEgressPolicy:
    settings = get_settings()
    return VideoEgressPolicy(
        settings.video_allowed_hosts,
        settings.video_network_timeout_seconds,
        resolver=socket.getaddrinfo,
    )


def _validate_download_info_egress(info: dict[str, Any], policy: VideoEgressPolicy) -> None:
    selected = info.get("requested_downloads") or info.get("requested_formats") or [info]
    if not isinstance(selected, list) or not selected:
        raise ValueError("Video extractor did not provide a safe downloadable stream")
    for item in selected:
        if not isinstance(item, dict):
            raise ValueError("Video extractor returned an invalid stream")
        protocol = str(item.get("protocol") or "https").lower()
        if protocol not in {"http", "https", "m3u8_native", "http_dash_segments"}:
            raise ValueError("Video stream requires an unsupported external transport")
        stream_url = str(item.get("url") or "")
        if not stream_url:
            raise ValueError("Video extractor did not provide a stream URL")
        policy.resolve(stream_url)
        fragment_base = str(item.get("fragment_base_url") or item.get("manifest_url") or stream_url)
        if item.get("manifest_url"):
            policy.resolve(str(item["manifest_url"]))
        fragments = item.get("fragments") or []
        if not isinstance(fragments, list):
            raise ValueError("Video extractor returned invalid stream fragments")
        for fragment in fragments:
            if not isinstance(fragment, dict) or not fragment.get("url"):
                raise ValueError("Video extractor returned an invalid stream fragment")
            policy.resolve(urljoin(fragment_base, str(fragment["url"])))


def extract_keyframes(
    video_id: str,
    video_path: Path,
    original_filename: str,
    max_keyframes: int = 8,
    source_url: str | None = None,
    extracted_context: str = "",
    transcript: str = "",
    visual_quality: str = "local",
    organization_id: str = LEGACY_ORGANIZATION_ID,
) -> VideoKeyframeResponse:
    if max_keyframes < 1 or max_keyframes > 16:
        raise ValueError("max_keyframes must be between 1 and 16")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("Unable to open uploaded video")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        duration = frame_count / fps if fps > 0 else 0.0
        _reject_duration(duration)
        organization_keyframe_dir = organization_storage_path(KEYFRAME_DIR, organization_id)
        output_dir = organization_keyframe_dir / video_id
        output_dir.mkdir(parents=True, exist_ok=True)

        notes: list[str] = []
        if frame_count == 0:
            return VideoKeyframeResponse(
                video_id=video_id,
                original_filename=original_filename,
                source_url=source_url,
                frame_count=0,
                fps=max(fps, 0.0),
                duration_seconds=0.0,
                keyframes=[],
                extracted_context=extracted_context,
                transcript=transcript,
                visual_quality=visual_quality,
                notes=["Видео не содержит доступных кадров."],
            )

        candidate_indices = _candidate_frame_indices(frame_count, max(max_keyframes * 6, 12))
        candidates: list[KeyframeCandidate] = []
        previous_gray: np.ndarray | None = None

        for frame_index in candidate_indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            scene_change = float(cv2.absdiff(gray, previous_gray).mean()) if previous_gray is not None else 0.0
            candidates.append(_score_keyframe_candidate(frame_index, frame, gray, fps, scene_change))
            previous_gray = gray

        selected = _select_high_value_candidates(candidates, max_keyframes)
        keyframes: list[Keyframe] = []
        failed_writes = 0
        for candidate in selected:
            image_name = f"frame_{len(keyframes) + 1:02d}.jpg"
            image_path = output_dir / image_name
            if not cv2.imwrite(str(image_path), candidate.frame):
                failed_writes += 1
                continue
            keyframes.append(
                Keyframe(
                    frame_index=candidate.frame_index,
                    timestamp_seconds=round(candidate.timestamp_seconds, 2),
                    image_path=str(image_path.relative_to(PROJECT_ROOT)),
                    image_url=(
                        f"/generated/keyframes/{video_id}/{image_name}"
                        if organization_id == LEGACY_ORGANIZATION_ID
                        else f"/generated/keyframes/{organization_id}/{video_id}/{image_name}"
                    ),
                    selection_score=round(candidate.score, 4),
                    selection_reason=_selection_reason(candidate),
                )
            )

        if failed_writes:
            notes.append(f"Не удалось сохранить часть выбранных кадров: {failed_writes}.")
        if not keyframes:
            notes.append("Не удалось извлечь ключевые кадры из видео.")
        elif len(keyframes) < max_keyframes:
            notes.append("Извлечено меньше кадров, чем запрошено: похожие или недоступные кадры были пропущены.")
        else:
            notes.append("Ключевые кадры выбраны по информативности: смена сцены, резкость, яркость, контраст и временное покрытие.")

        return VideoKeyframeResponse(
            video_id=video_id,
            original_filename=original_filename,
            source_url=source_url,
            frame_count=frame_count,
            fps=round(fps, 3),
            duration_seconds=round(duration, 2),
            keyframes=keyframes,
            extracted_context=extracted_context,
            transcript=transcript,
            visual_quality=visual_quality,
            notes=notes,
        )
    finally:
        capture.release()


def _candidate_frame_indices(frame_count: int, count: int) -> list[int]:
    if frame_count <= 1:
        return [0]
    count = max(1, min(count, frame_count))
    if count == 1:
        return [0]
    return sorted({round(i * (frame_count - 1) / (count - 1)) for i in range(count)})


def _score_keyframe_candidate(
    frame_index: int,
    frame: np.ndarray,
    gray: np.ndarray,
    fps: float,
    scene_change: float,
) -> KeyframeCandidate:
    sharpness_raw = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness_raw = float(gray.mean())
    contrast_raw = float(gray.std())
    scene_score = min(scene_change / 35.0, 1.0)
    sharpness_score = min(sharpness_raw / 400.0, 1.0)
    brightness_score = max(0.0, 1.0 - abs(brightness_raw - 127.0) / 127.0)
    contrast_score = min(contrast_raw / 64.0, 1.0)
    score = (
        0.42 * scene_score
        + 0.26 * sharpness_score
        + 0.18 * contrast_score
        + 0.14 * brightness_score
    )
    return KeyframeCandidate(
        frame_index=frame_index,
        frame=frame,
        gray=gray,
        timestamp_seconds=frame_index / fps if fps > 0 else 0.0,
        scene_change=scene_change,
        sharpness=sharpness_raw,
        brightness_score=brightness_score,
        contrast_score=contrast_score,
        score=score,
    )


def _select_high_value_candidates(
    candidates: list[KeyframeCandidate],
    max_keyframes: int,
) -> list[KeyframeCandidate]:
    if not candidates or max_keyframes <= 0:
        return []
    selected: list[KeyframeCandidate] = []
    ordered_by_time = sorted(candidates, key=lambda candidate: candidate.frame_index)
    bucket_count = min(max_keyframes, len(ordered_by_time))
    for bucket_index in range(bucket_count):
        bucket = _candidate_bucket(ordered_by_time, bucket_index, bucket_count)
        for candidate in sorted(bucket, key=lambda item: item.score, reverse=True):
            if _is_visually_distinct(candidate, selected):
                selected.append(candidate)
                break
        if len(selected) >= max_keyframes:
            break
    ordered_by_score = sorted(ordered_by_time, key=lambda candidate: candidate.score, reverse=True)
    for candidate in ordered_by_score:
        if len(selected) >= max_keyframes:
            break
        if candidate.frame_index in {item.frame_index for item in selected}:
            continue
        if _is_visually_distinct(candidate, selected):
            selected.append(candidate)
    return sorted(selected, key=lambda candidate: candidate.frame_index)


def _candidate_bucket(
    candidates: list[KeyframeCandidate],
    bucket_index: int,
    bucket_count: int,
) -> list[KeyframeCandidate]:
    start = round(bucket_index * len(candidates) / bucket_count)
    end = round((bucket_index + 1) * len(candidates) / bucket_count)
    return candidates[start:max(start + 1, end)]


def _is_visually_distinct(candidate: KeyframeCandidate, selected: list[KeyframeCandidate]) -> bool:
    for item in selected:
        difference = float(cv2.absdiff(candidate.gray, item.gray).mean())
        if difference < MIN_KEYFRAME_DIFFERENCE:
            return False
    return True


def _selection_reason(candidate: KeyframeCandidate) -> str:
    reasons = []
    if candidate.scene_change >= 8.0:
        reasons.append("заметная смена сцены")
    if candidate.sharpness >= 120.0:
        reasons.append("достаточная резкость")
    if candidate.contrast_score >= 0.35:
        reasons.append("контрастные детали")
    if candidate.brightness_score >= 0.6:
        reasons.append("нормальная яркость")
    return ", ".join(reasons or ["временное покрытие операции"])


def _normalize_visual_quality(visual_quality: int | str) -> int:
    value = str(visual_quality).lower().strip().removesuffix("p")
    try:
        height = int(value)
    except ValueError as exc:
        raise ValueError("visual_quality must be one of: 240, 360, 720, 1080") from exc
    if height not in VISUAL_QUALITY_HEIGHTS:
        raise ValueError("visual_quality must be one of: 240, 360, 720, 1080")
    return height


def _format_for_visual_quality(height: int) -> str:
    return (
        f"bestvideo[height<={height}][ext=mp4]/"
        f"best[height<={height}][ext=mp4]/"
        f"bestvideo[height<={height}]/"
        f"best[height<={height}]"
    )


def _extract_transcript(info: dict, *, policy: VideoEgressPolicy | None = None) -> str:
    policy = policy or _video_egress_policy()
    preferred_languages = ["ru-orig", "ru", "en-orig", "en"]
    subtitle_groups = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
    for tracks_by_language in subtitle_groups:
        for language in preferred_languages:
            tracks = tracks_by_language.get(language)
            transcript = _extract_transcript_from_tracks(tracks or [], policy=policy)
            if transcript:
                return transcript[:TRANSCRIPT_LIMIT]
    for tracks_by_language in subtitle_groups:
        for tracks in tracks_by_language.values():
            transcript = _extract_transcript_from_tracks(tracks or [], policy=policy)
            if transcript:
                return transcript[:TRANSCRIPT_LIMIT]
    return ""


def _extract_transcript_from_tracks(
    tracks: list[dict],
    *,
    policy: VideoEgressPolicy | None = None,
) -> str:
    json_track = next((track for track in tracks if track.get("ext") == "json3" and track.get("url")), None)
    if not json_track:
        return ""
    try:
        policy = policy or _video_egress_policy()
        subtitle_url = str(json_track["url"])
        policy.resolve(subtitle_url)
        with policy.open(subtitle_url) as response:
            content = response.read(TRANSCRIPT_TRACK_MAX_BYTES + 1)
        if len(content) > TRANSCRIPT_TRACK_MAX_BYTES:
            return ""
        payload = json.loads(content.decode("utf-8"))
    except Exception:
        return ""
    pieces: list[str] = []
    for event in payload.get("events", []):
        segments = event.get("segs") or []
        text = "".join(segment.get("utf8", "") for segment in segments)
        cleaned = _clean_text(text)
        if cleaned:
            pieces.append(cleaned)
    return _dedupe_transcript(" ".join(pieces))


def _build_extracted_context(metadata: dict[str, str]) -> str:
    parts = [
        f"Название видео: {metadata.get('title', '').strip()}",
        f"Ссылка: {metadata.get('source_url', '').strip()}",
    ]
    description = metadata.get("description", "").strip()
    if description:
        parts.append(f"Описание видео:\n{description[:2500]}")
    else:
        parts.append("Описание видео не найдено: проверить назначение операции по визуальным кадрам и локальной документации.")
    transcript = metadata.get("transcript", "").strip()
    if transcript:
        parts.append(f"Распознанная речь/субтитры:\n{transcript[:3500]}")
    else:
        parts.append("Субтитры или распознанная речь не найдены: инструкция должна опираться на название, ключевые кадры и экспертную проверку.")
    return "\n\n".join(part for part in parts if part.strip())[:CONTEXT_LIMIT]


def _reject_known_oversized_video(info: dict) -> None:
    duration = info.get("duration")
    if isinstance(duration, (int, float)) and duration > 0:
        _reject_duration(float(duration))
    known_sizes = [
        value
        for key in ("filesize", "filesize_approx")
        if isinstance((value := info.get(key)), int) and value > 0
    ]
    for item in info.get("formats") or []:
        if not isinstance(item, dict):
            continue
        known_sizes.extend(
            value
            for key in ("filesize", "filesize_approx")
            if isinstance((value := item.get(key)), int) and value > 0
        )
    if not known_sizes:
        return
    max_bytes = get_settings().video_max_bytes
    if min(known_sizes) > max_bytes:
        raise ValueError(f"Video is too large. Maximum size is {max_bytes // (1024 * 1024)} MB")


def _reject_duration(duration_seconds: float) -> None:
    max_duration = get_settings().video_max_duration_seconds
    if duration_seconds > max_duration:
        raise ValueError(f"Video is too long. Maximum duration is {round(max_duration)} seconds")


def _clean_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _dedupe_transcript(text: str) -> str:
    words = text.split()
    if not words:
        return ""
    compact: list[str] = []
    previous = ""
    for word in words:
        if word == previous and len(word) > 2:
            continue
        compact.append(word)
        previous = word
    return " ".join(compact)
