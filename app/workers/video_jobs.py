from __future__ import annotations

import threading
from contextlib import AbstractContextManager
from pathlib import Path
import uuid
from typing import Any

from app.core.authorization import register_resource_ownership
from app.core.organization import organization_storage_path
from app.core.settings import Settings, get_settings
from app.schemas.video import VideoKeyframeResponse
from app.storage.video_jobs import (
    VideoJob,
    cancel_claimed_video_job,
    claim_next_video_job,
    complete_video_job,
    fail_video_job,
    heartbeat_video_job,
    set_video_job_artifact,
    update_video_job_progress,
    video_job_cancel_requested,
)
from app.storage.database import apply_migrations, connect_database
from app.vision import keyframes as keyframe_storage
from app.vision.keyframes import remove_video_download_candidates
from app.vision.processing import cleanup_video_artifacts
from app.workers.stage_process import (
    StageInterruptedError,
    StageTimeoutError,
    run_isolated_stage,
)


class JobCancelled(Exception):
    pass


_run_stage = run_isolated_stage


class LeaseHeartbeat(AbstractContextManager["LeaseHeartbeat"]):
    def __init__(self, job_id: str, worker_id: str, settings: Settings) -> None:
        self.job_id = job_id
        self.worker_id = worker_id
        self.settings = settings
        self.lost = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "LeaseHeartbeat":
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self.settings.video_job_heartbeat_seconds + 1)

    def _run(self) -> None:
        while not self._stop.wait(self.settings.video_job_heartbeat_seconds):
            try:
                active = heartbeat_video_job(
                    self.job_id,
                    self.worker_id,
                    lease_seconds=self.settings.video_job_lease_seconds,
                    database_path=self.settings.database_path,
                )
            except Exception:
                self.lost.set()
                return
            if not active:
                self.lost.set()
                return


def run_one_video_job(worker_id: str, *, settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    job = claim_next_video_job(
        worker_id,
        lease_seconds=active_settings.video_job_lease_seconds,
        database_path=active_settings.database_path,
    )
    if job is None:
        return False
    with LeaseHeartbeat(job.job_id, worker_id, active_settings) as heartbeat:
        _process_claimed_job(job, worker_id, active_settings, heartbeat)
    return True


def _process_claimed_job(
    job: VideoJob,
    worker_id: str,
    settings: Settings,
    heartbeat: LeaseHeartbeat,
) -> None:
    video_id = job.video_id
    video_path = Path(job.artifact_path) if job.artifact_path else None
    try:
        _checkpoint(job, worker_id, settings, heartbeat, "preparing", 5)
        if job.source_kind == "upload":
            if not video_id or video_path is None:
                raise ValueError("Uploaded video job is missing its staged artifact")
            video_path = _validated_upload_path(video_path, job.organization_id)
            metadata = {
                "title": str(job.request_payload["original_filename"]),
                "source_url": None,
                "extracted_context": "",
                "transcript": "",
                "visual_quality": "uploaded",
            }
        else:
            if video_id and video_path is not None:
                cleanup_video_artifacts(video_id, video_path, job.organization_id)
            _checkpoint(job, worker_id, settings, heartbeat, "downloading", 12)
            video_id = uuid.uuid4().hex
            download_result = _run_blocking_stage(
                "download",
                {
                    "video_url": str(job.request_payload["video_url"]),
                    "visual_quality": str(job.request_payload["visual_quality"]),
                    "organization_id": job.organization_id,
                    "video_id": video_id,
                },
                timeout_seconds=settings.video_job_download_timeout_seconds,
                job=job,
                worker_id=worker_id,
                settings=settings,
                heartbeat=heartbeat,
            )
            video_id = str(download_result["video_id"])
            video_path = Path(str(download_result["video_path"]))
            metadata = dict(download_result["metadata"])
            if not set_video_job_artifact(
                job.job_id,
                worker_id,
                video_id,
                str(video_path.resolve()),
                database_path=settings.database_path,
            ):
                raise RuntimeError("Video job lease was lost while recording the download")
        _checkpoint(job, worker_id, settings, heartbeat, "extracting_keyframes", 38)
        extract_result = _run_blocking_stage(
            "extract",
            {
                "video_id": video_id,
                "video_path": str(video_path),
                "original_filename": str(metadata["title"]),
                "max_keyframes": int(job.request_payload["max_keyframes"]),
                "source_url": str(metadata["source_url"]) if metadata.get("source_url") else None,
                "extracted_context": str(metadata.get("extracted_context") or ""),
                "transcript": str(metadata.get("transcript") or ""),
                "visual_quality": str(metadata.get("visual_quality") or "local"),
                "organization_id": job.organization_id,
            },
            timeout_seconds=settings.video_job_extract_timeout_seconds,
            job=job,
            worker_id=worker_id,
            settings=settings,
            heartbeat=heartbeat,
        )
        response = VideoKeyframeResponse.model_validate(extract_result)
        _checkpoint(job, worker_id, settings, heartbeat, "analyzing_frames", 72)
        _scope_response(response, job)
        analysis_result = _run_blocking_stage(
            "analyze",
            {"response": response.model_dump(mode="json"), "source_kind": job.source_kind},
            timeout_seconds=settings.video_job_analysis_timeout_seconds,
            job=job,
            worker_id=worker_id,
            settings=settings,
            heartbeat=heartbeat,
        )
        response = VideoKeyframeResponse.model_validate(analysis_result)
        _checkpoint(job, worker_id, settings, heartbeat, "finalizing", 92)
        register_resource_ownership(
            job.organization_id,
            job.project_id,
            "video",
            video_id,
            job.owner_user_id,
            database_path=settings.database_path,
        )
        if not complete_video_job(
            job.job_id,
            worker_id,
            response.model_dump(mode="json"),
            database_path=settings.database_path,
        ):
            cleanup_video_artifacts(video_id, video_path, job.organization_id)
            _remove_video_ownership(job, video_id, settings)
            cancel_claimed_video_job(job.job_id, worker_id, database_path=settings.database_path)
    except JobCancelled:
        if video_id and video_path is not None:
            cleanup_video_artifacts(video_id, video_path, job.organization_id)
        cancel_claimed_video_job(job.job_id, worker_id, database_path=settings.database_path)
    except StageTimeoutError as exc:
        if job.source_kind == "url" and exc.stage == "download" and video_id:
            remove_video_download_candidates(video_id, job.organization_id)
        failed = fail_video_job(
            job.job_id,
            worker_id,
            "processing_timeout",
            "Video processing exceeded the configured time limit.",
            retryable=True,
            database_path=settings.database_path,
        )
        if failed is not None and failed.status != "queued" and video_id and video_path is not None:
            cleanup_video_artifacts(video_id, video_path, job.organization_id)
    except ValueError as exc:
        code, message, retryable = _public_error(exc, job.source_kind)
        failed = fail_video_job(
            job.job_id,
            worker_id,
            code,
            message,
            retryable=retryable,
            database_path=settings.database_path,
        )
        if failed is not None and (failed.status != "queued" or job.source_kind == "url"):
            if video_id and video_path is not None:
                cleanup_video_artifacts(video_id, video_path, job.organization_id)
    except Exception:
        failed = fail_video_job(
            job.job_id,
            worker_id,
            "processing_failed",
            "Video processing stopped unexpectedly and may be retried.",
            retryable=True,
            database_path=settings.database_path,
        )
        if failed is not None and failed.status != "queued" and video_id and video_path is not None:
            cleanup_video_artifacts(video_id, video_path, job.organization_id)


def _run_blocking_stage(
    stage: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    job: VideoJob,
    worker_id: str,
    settings: Settings,
    heartbeat: LeaseHeartbeat,
) -> dict[str, Any]:
    try:
        return _run_stage(
            stage,
            payload,
            timeout_seconds=timeout_seconds,
            poll_seconds=settings.video_job_stage_poll_seconds,
            interrupt_reason=lambda: _stage_interrupt_reason(job, worker_id, settings, heartbeat),
        )
    except StageInterruptedError as exc:
        if exc.reason == "cancelled":
            raise JobCancelled from None
        raise RuntimeError("Video job lease was lost during a blocking stage") from None


def _stage_interrupt_reason(
    job: VideoJob,
    worker_id: str,
    settings: Settings,
    heartbeat: LeaseHeartbeat,
) -> str | None:
    if heartbeat.lost.is_set():
        return "lease_lost"
    if video_job_cancel_requested(job.job_id, worker_id, database_path=settings.database_path):
        return "cancelled"
    return None


def _checkpoint(
    job: VideoJob,
    worker_id: str,
    settings: Settings,
    heartbeat: LeaseHeartbeat,
    stage: str,
    progress: int,
) -> None:
    if heartbeat.lost.is_set():
        raise RuntimeError("Video job lease was lost")
    if video_job_cancel_requested(job.job_id, worker_id, database_path=settings.database_path):
        raise JobCancelled
    if not update_video_job_progress(
        job.job_id,
        worker_id,
        stage,
        progress,
        database_path=settings.database_path,
    ):
        raise RuntimeError("Video job lease was lost")


def _validated_upload_path(video_path: Path, organization_id: str) -> Path:
    resolved = video_path.resolve(strict=False)
    allowed_root = organization_storage_path(keyframe_storage.UPLOAD_DIR, organization_id).resolve(strict=False)
    try:
        resolved.relative_to(allowed_root)
    except ValueError:
        raise ValueError("Uploaded video job contains an invalid artifact path") from None
    if not resolved.is_file():
        raise ValueError("Uploaded video artifact is no longer available")
    return resolved


def _scope_response(response: VideoKeyframeResponse, job: VideoJob) -> None:
    response.organization_id = job.organization_id
    response.project_id = job.project_id
    response.owner_user_id = job.owner_user_id


def _public_error(exc: ValueError, source_kind: str) -> tuple[str, str, bool]:
    message = str(exc)
    if source_kind == "url" and ("download" in message.lower() or "metadata" in message.lower()):
        return "download_failed", "The video could not be downloaded from the permitted URL.", True
    return "invalid_video", "The video could not be processed. Verify its format, size, and duration.", False


def _remove_video_ownership(job: VideoJob, video_id: str, settings: Settings) -> None:
    with connect_database(settings.database_path) as connection:
        apply_migrations(connection)
        connection.execute(
            """
            DELETE FROM resource_ownership
            WHERE organization_id = ? AND project_id = ?
              AND resource_type = 'video' AND resource_id = ?
            """,
            (job.organization_id, job.project_id, video_id),
        )
        connection.commit()
