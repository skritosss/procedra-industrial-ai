import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile, status

from app.core.authorization import register_resource_ownership, require_permission
from app.core.organization import organization_storage_path
from app.core.settings import get_settings
from app.schemas.video import VideoKeyframeResponse
from app.schemas.video_jobs import VideoJobResponse
from app.storage.video_jobs import (
    VideoJob,
    VideoSourceKind,
    create_video_job,
    find_video_job_by_idempotency_key,
    get_video_job,
    request_video_job_cancellation,
)
from app.vision import keyframes as keyframe_storage
from app.vision.keyframes import download_video_from_url, extract_keyframes, save_uploaded_video_stream
from app.vision.processing import add_url_processing_notes, attach_frame_analysis


router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("/keyframes", response_model=VideoKeyframeResponse)
def create_video_keyframes(
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
        video_id, video_path = save_uploaded_video_stream(
            file.filename or "uploaded.mp4",
            file.file,
            max_bytes=max_bytes,
            organization_id=context.organization_id,
        )
        try:
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
            _attach_frame_analysis(response)
            register_resource_ownership(
                context.organization_id,
                context.project_id,
                "video",
                video_id,
                response.owner_user_id,
                database_path=settings.database_path,
            )
            return response
        except Exception:
            _cleanup_video_artifacts(video_id, video_path, context.organization_id)
            raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/keyframes-from-url", response_model=VideoKeyframeResponse)
def create_video_keyframes_from_url(
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
        try:
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
            add_url_processing_notes(response)
            _attach_frame_analysis(response)
            register_resource_ownership(
                context.organization_id,
                context.project_id,
                "video",
                video_id,
                response.owner_user_id,
                database_path=settings.database_path,
            )
            return response
        except Exception:
            _cleanup_video_artifacts(video_id, video_path, context.organization_id)
            raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validate_max_keyframes(max_keyframes: int) -> None:
    if max_keyframes < 1 or max_keyframes > 16:
        raise ValueError("max_keyframes must be between 1 and 16")


def _attach_frame_analysis(response: VideoKeyframeResponse) -> None:
    attach_frame_analysis(response)


def _cleanup_video_artifacts(video_id: str, video_path: Path, organization_id: str) -> None:
    video_path.unlink(missing_ok=True)
    keyframe_dir = organization_storage_path(keyframe_storage.KEYFRAME_DIR, organization_id) / video_id
    if keyframe_dir.is_dir():
        shutil.rmtree(keyframe_dir)


@router.post("/jobs", response_model=VideoJobResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_video_job(
    request: Request,
    file: UploadFile | None = File(None),
    video_url: str = Form(""),
    max_keyframes: int = Form(8),
    visual_quality: str = Form("720"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> VideoJobResponse:
    settings = get_settings()
    context = require_permission(request, "video:create", settings)
    key = _normalize_idempotency_key(idempotency_key)
    existing = find_video_job_by_idempotency_key(
        context.organization_id,
        context.project_id,
        key,
        database_path=settings.database_path,
    )
    if existing is not None:
        return _video_job_response(existing)
    _validate_max_keyframes(max_keyframes)
    normalized_url = video_url.strip()
    if (file is None) == (not normalized_url):
        raise HTTPException(status_code=400, detail="Provide exactly one video file or video URL")

    video_id: str | None = None
    video_path: Path | None = None
    source_kind: VideoSourceKind
    try:
        if file is not None:
            if file.size is not None and file.size > settings.video_max_bytes:
                raise ValueError(
                    f"Video file is too large. Maximum size is {settings.video_max_bytes // (1024 * 1024)} MB"
                )
            video_id, video_path = save_uploaded_video_stream(
                file.filename or "uploaded.mp4",
                file.file,
                max_bytes=settings.video_max_bytes,
                organization_id=context.organization_id,
            )
            source_kind = "upload"
            payload = {
                "original_filename": file.filename or "uploaded video",
                "max_keyframes": max_keyframes,
            }
        else:
            source_kind = "url"
            payload = {
                "video_url": normalized_url,
                "visual_quality": visual_quality,
                "max_keyframes": max_keyframes,
            }
        job, created = create_video_job(
            context.organization_id,
            context.project_id,
            context.user.user_id if context.user else None,
            source_kind,
            payload,
            key,
            video_id=video_id,
            artifact_path=str(video_path.resolve()) if video_path is not None else None,
            max_attempts=settings.video_job_max_attempts,
            database_path=settings.database_path,
        )
        if not created and video_id and video_path is not None:
            _cleanup_video_artifacts(video_id, video_path, context.organization_id)
        return _video_job_response(job)
    except ValueError as exc:
        if video_id and video_path is not None:
            _cleanup_video_artifacts(video_id, video_path, context.organization_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=VideoJobResponse)
def read_video_job(job_id: str, request: Request) -> VideoJobResponse:
    settings = get_settings()
    context = require_permission(request, "video:read", settings)
    job = get_video_job(
        job_id,
        context.organization_id,
        context.project_id,
        database_path=settings.database_path,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Video job not found")
    return _video_job_response(job)


@router.get("/jobs/{job_id}/result", response_model=VideoKeyframeResponse)
def read_video_job_result(job_id: str, request: Request) -> VideoKeyframeResponse:
    settings = get_settings()
    context = require_permission(request, "video:read", settings)
    job = get_video_job(
        job_id,
        context.organization_id,
        context.project_id,
        database_path=settings.database_path,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Video job not found")
    if job.status != "succeeded" or job.result_payload is None:
        raise HTTPException(status_code=409, detail="Video job result is not available")
    return VideoKeyframeResponse.model_validate(job.result_payload)


@router.delete("/jobs/{job_id}", response_model=VideoJobResponse)
def cancel_video_job(job_id: str, request: Request) -> VideoJobResponse:
    settings = get_settings()
    context = require_permission(request, "video:create", settings)
    job = request_video_job_cancellation(
        job_id,
        context.organization_id,
        context.project_id,
        database_path=settings.database_path,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Video job not found")
    if job.status == "cancelled":
        _cleanup_cancelled_upload_job(job)
    return _video_job_response(job)


def _normalize_idempotency_key(value: str | None) -> str:
    if value is None:
        return os.urandom(16).hex()
    key = value.strip()
    if len(key) < 8 or len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key must contain between 8 and 128 characters")
    if any(ord(character) < 33 or ord(character) > 126 for character in key):
        raise HTTPException(status_code=400, detail="Idempotency-Key contains unsupported characters")
    return key


def _video_job_response(job: VideoJob) -> VideoJobResponse:
    return VideoJobResponse(
        job_id=job.job_id,
        status=job.status,
        stage=job.stage,
        progress_percent=job.progress_percent,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        cancel_requested=job.cancel_requested,
        result_available=job.status == "succeeded" and job.result_payload is not None,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        updated_at=job.updated_at,
    )


def _cleanup_cancelled_upload_job(job: VideoJob) -> None:
    if job.source_kind != "upload" or not job.video_id or not job.artifact_path:
        return
    artifact = Path(job.artifact_path).resolve(strict=False)
    allowed_root = organization_storage_path(
        keyframe_storage.UPLOAD_DIR,
        job.organization_id,
    ).resolve(strict=False)
    try:
        artifact.relative_to(allowed_root)
    except ValueError:
        return
    _cleanup_video_artifacts(job.video_id, artifact, job.organization_id)
