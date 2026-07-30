import shutil
from pathlib import Path

from app.core.organization import organization_storage_path
from app.schemas.video import VIDEO_EXTRACTED_CONTEXT_MAX_LENGTH, VideoKeyframeResponse
from app.vision import keyframes as keyframe_storage
from app.vision.frame_analysis import (
    analyze_keyframes,
    build_frame_analysis_context,
    build_video_segment_context,
    build_video_segments,
)


def attach_frame_analysis(response: VideoKeyframeResponse) -> None:
    response.frame_analyses = analyze_keyframes(response.keyframes)
    frame_context = build_frame_analysis_context(response.frame_analyses)
    response.video_segments = build_video_segments(
        response.keyframes,
        response.frame_analyses,
        response.duration_seconds,
    )
    segment_context = build_video_segment_context(response.video_segments)
    if frame_context or segment_context:
        combined_context = "\n\n".join(
            part for part in [response.extracted_context, segment_context, frame_context] if part
        )
        response.extracted_context = combined_context[:VIDEO_EXTRACTED_CONTEXT_MAX_LENGTH].rstrip()
        modes = sorted({analysis.analysis_mode for analysis in response.frame_analyses})
        response.notes.append(f"Анализ ключевых кадров добавлен в контекст инструкции: {', '.join(modes)}.")
    if response.video_segments:
        response.notes.append(f"Видео разбито на смысловые этапы: {len(response.video_segments)}.")


def cleanup_video_artifacts(video_id: str, video_path: Path, organization_id: str) -> None:
    video_path.unlink(missing_ok=True)
    keyframe_dir = organization_storage_path(keyframe_storage.KEYFRAME_DIR, organization_id) / video_id
    if keyframe_dir.is_dir():
        shutil.rmtree(keyframe_dir)


def add_url_processing_notes(response: VideoKeyframeResponse) -> None:
    response.notes.append(
        "Видео загружено по ссылке. Используйте только материалы, на которые у вас есть права или разрешение."
    )
    response.notes.append(
        "Текстовые данные получены отдельно от видеопотока; "
        f"кадры извлечены из потока качества {response.visual_quality}."
    )
    if response.transcript:
        response.notes.append("Контекст для инструкции собран из названия, описания и субтитров видео.")
    else:
        response.notes.append(
            "Субтитры не найдены: контекст для инструкции собран из названия, описания и таймкодов кадров."
        )
