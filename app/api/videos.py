from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.core.authorization import register_resource_ownership, require_permission
from app.core.settings import get_settings
from app.schemas.video import VideoKeyframeResponse
from app.vision.frame_analysis import (
    analyze_keyframes,
    build_frame_analysis_context,
    build_video_segment_context,
    build_video_segments,
)
from app.vision.keyframes import download_video_from_url, extract_keyframes, save_uploaded_video


router = APIRouter(prefix="/videos", tags=["videos"])
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024


@router.post("/keyframes", response_model=VideoKeyframeResponse)
async def create_video_keyframes(
    request: Request,
    file: UploadFile = File(...),
    max_keyframes: int = Form(8),
) -> VideoKeyframeResponse:
    settings = get_settings()
    try:
        context = require_permission(request, "video:create", settings)
        _validate_max_keyframes(max_keyframes)
        max_bytes = settings.video_max_bytes
        if file.size is not None and file.size > max_bytes:
            raise ValueError(
                f"Video file is too large. Maximum size is {max_bytes // (1024 * 1024)} MB"
            )
        content = await _read_upload_limited(file, max_bytes)
        if not content:
            raise ValueError("Uploaded video is empty")
        video_id, video_path = save_uploaded_video(
            file.filename or "uploaded.mp4",
            content,
            organization_id=context.organization_id,
        )
        response = extract_keyframes(
            video_id=video_id,
            video_path=video_path,
            original_filename=file.filename or "uploaded video",
            max_keyframes=max_keyframes,
            visual_quality="uploaded",
            organization_id=context.organization_id,
        )
        response.organization_id = context.organization_id
        response.project_id = context.project_id
        response.owner_user_id = context.user.user_id if context.user else None
        register_resource_ownership(
            context.organization_id,
            context.project_id,
            "video",
            video_id,
            response.owner_user_id,
            database_path=settings.database_path,
        )
        _attach_frame_analysis(response)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"Video file is too large. Maximum size is {max_bytes // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/keyframes-from-url", response_model=VideoKeyframeResponse)
async def create_video_keyframes_from_url(
    request: Request,
    video_url: str = Form(""),
    max_keyframes: int = Form(8),
    visual_quality: str = Form("720"),
) -> VideoKeyframeResponse:
    settings = get_settings()
    try:
        context = require_permission(request, "video:create", settings)
        if not video_url.strip():
            raise ValueError("Video URL is required")
        _validate_max_keyframes(max_keyframes)
        video_id, video_path, metadata = download_video_from_url(
            video_url.strip(),
            visual_quality,
            organization_id=context.organization_id,
        )
        response = extract_keyframes(
            video_id=video_id,
            video_path=video_path,
            original_filename=metadata["title"],
            max_keyframes=max_keyframes,
            source_url=metadata.get("source_url"),
            extracted_context=metadata.get("extracted_context", ""),
            transcript=metadata.get("transcript", ""),
            visual_quality=metadata.get("visual_quality", f"{visual_quality}p"),
            organization_id=context.organization_id,
        )
        response.organization_id = context.organization_id
        response.project_id = context.project_id
        response.owner_user_id = context.user.user_id if context.user else None
        register_resource_ownership(
            context.organization_id,
            context.project_id,
            "video",
            video_id,
            response.owner_user_id,
            database_path=settings.database_path,
        )
        response.notes.append("Видео загружено по ссылке. Используйте только материалы, на которые у вас есть права или разрешение.")
        response.notes.append(f"Текстовые данные получены отдельно от видеопотока; кадры извлечены из потока качества {response.visual_quality}.")
        _attach_frame_analysis(response)
        if response.transcript:
            response.notes.append("Контекст для инструкции собран из названия, описания и субтитров видео.")
        else:
            response.notes.append("Субтитры не найдены: контекст для инструкции собран из названия, описания и таймкодов кадров.")
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _attach_frame_analysis(response: VideoKeyframeResponse) -> None:
    response.frame_analyses = analyze_keyframes(response.keyframes)
    frame_context = build_frame_analysis_context(response.frame_analyses)
    response.video_segments = build_video_segments(
        response.keyframes,
        response.frame_analyses,
        response.duration_seconds,
    )
    segment_context = build_video_segment_context(response.video_segments)
    if frame_context or segment_context:
        response.extracted_context = "\n\n".join(
            part for part in [response.extracted_context, segment_context, frame_context] if part
        )
        modes = sorted({analysis.analysis_mode for analysis in response.frame_analyses})
        response.notes.append(f"Анализ ключевых кадров добавлен в контекст инструкции: {', '.join(modes)}.")
    if response.video_segments:
        response.notes.append(f"Видео разбито на смысловые этапы: {len(response.video_segments)}.")


def _validate_max_keyframes(max_keyframes: int) -> None:
    if max_keyframes < 1 or max_keyframes > 16:
        raise ValueError("max_keyframes must be between 1 and 16")
