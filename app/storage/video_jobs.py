from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

from app.storage.database import apply_migrations, connect_database


VideoJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
VideoSourceKind = Literal["upload", "url"]


@dataclass(frozen=True)
class VideoJob:
    job_id: str
    organization_id: str
    project_id: str
    owner_user_id: str | None
    source_kind: VideoSourceKind
    status: VideoJobStatus
    stage: str
    progress_percent: int
    request_payload: dict[str, Any]
    result_payload: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    idempotency_key: str
    video_id: str | None
    artifact_path: str | None
    attempts: int
    max_attempts: int
    available_at: datetime
    lease_owner: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    cancel_requested_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime

    @property
    def cancel_requested(self) -> bool:
        return self.cancel_requested_at is not None


def create_video_job(
    organization_id: str,
    project_id: str,
    owner_user_id: str | None,
    source_kind: VideoSourceKind,
    request_payload: dict[str, Any],
    idempotency_key: str,
    *,
    video_id: str | None = None,
    artifact_path: str | None = None,
    max_attempts: int = 3,
    database_path: Path | None = None,
) -> tuple[VideoJob, bool]:
    now = datetime.now(UTC).isoformat()
    job_id = os.urandom(16).hex()
    serialized_request = json.dumps(request_payload, ensure_ascii=False, sort_keys=True)
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM video_jobs
                WHERE organization_id = ? AND project_id = ? AND idempotency_key = ?
                """,
                (organization_id, project_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return _job_from_row(existing), False
            connection.execute(
                """
                INSERT INTO video_jobs (
                    job_id, organization_id, project_id, owner_user_id, job_type,
                    source_kind, status, stage, progress_percent, request_json,
                    idempotency_key, video_id, artifact_path, max_attempts,
                    available_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'extract_keyframes', ?, 'queued', 'queued', 0, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    organization_id,
                    project_id,
                    owner_user_id,
                    source_kind,
                    serialized_request,
                    idempotency_key,
                    video_id,
                    artifact_path,
                    max_attempts,
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute("SELECT * FROM video_jobs WHERE job_id = ?", (job_id,)).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    if row is None:
        raise RuntimeError("Video job was not persisted")
    return _job_from_row(row), True


def get_video_job(
    job_id: str,
    organization_id: str,
    project_id: str,
    *,
    database_path: Path | None = None,
) -> VideoJob | None:
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        row = connection.execute(
            """
            SELECT * FROM video_jobs
            WHERE job_id = ? AND organization_id = ? AND project_id = ?
            """,
            (job_id, organization_id, project_id),
        ).fetchone()
    return _job_from_row(row) if row is not None else None


def find_video_job_by_idempotency_key(
    organization_id: str,
    project_id: str,
    idempotency_key: str,
    *,
    database_path: Path | None = None,
) -> VideoJob | None:
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        row = connection.execute(
            """
            SELECT * FROM video_jobs
            WHERE organization_id = ? AND project_id = ? AND idempotency_key = ?
            """,
            (organization_id, project_id, idempotency_key),
        ).fetchone()
    return _job_from_row(row) if row is not None else None


def claim_next_video_job(
    worker_id: str,
    *,
    lease_seconds: int,
    database_path: Path | None = None,
    now: datetime | None = None,
) -> VideoJob | None:
    current = now or datetime.now(UTC)
    current_iso = current.isoformat()
    lease_expires = (current + timedelta(seconds=lease_seconds)).isoformat()
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            _recover_expired_jobs(connection, current_iso)
            row = connection.execute(
                """
                SELECT job_id FROM video_jobs
                WHERE status = 'queued'
                  AND cancel_requested_at IS NULL
                  AND available_at <= ?
                ORDER BY created_at, job_id
                LIMIT 1
                """,
                (current_iso,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            job_id = str(row["job_id"])
            connection.execute(
                """
                UPDATE video_jobs
                SET status = 'running', stage = 'starting', progress_percent = 1,
                    attempts = attempts + 1, lease_owner = ?, lease_expires_at = ?,
                    heartbeat_at = ?, started_at = COALESCE(started_at, ?), updated_at = ?
                WHERE job_id = ? AND status = 'queued'
                """,
                (worker_id, lease_expires, current_iso, current_iso, current_iso, job_id),
            )
            claimed = connection.execute("SELECT * FROM video_jobs WHERE job_id = ?", (job_id,)).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return _job_from_row(claimed) if claimed is not None else None


def heartbeat_video_job(
    job_id: str,
    worker_id: str,
    *,
    lease_seconds: int,
    database_path: Path | None = None,
) -> bool:
    now = datetime.now(UTC)
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        result = connection.execute(
            """
            UPDATE video_jobs
            SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
            WHERE job_id = ? AND status = 'running' AND lease_owner = ?
            """,
            (
                now.isoformat(),
                (now + timedelta(seconds=lease_seconds)).isoformat(),
                now.isoformat(),
                job_id,
                worker_id,
            ),
        )
        connection.commit()
    return result.rowcount == 1


def update_video_job_progress(
    job_id: str,
    worker_id: str,
    stage: str,
    progress_percent: int,
    *,
    database_path: Path | None = None,
) -> bool:
    now = datetime.now(UTC).isoformat()
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        result = connection.execute(
            """
            UPDATE video_jobs SET stage = ?, progress_percent = ?, updated_at = ?
            WHERE job_id = ? AND status = 'running' AND lease_owner = ?
            """,
            (stage, max(0, min(progress_percent, 99)), now, job_id, worker_id),
        )
        connection.commit()
    return result.rowcount == 1


def set_video_job_artifact(
    job_id: str,
    worker_id: str,
    video_id: str,
    artifact_path: str,
    *,
    database_path: Path | None = None,
) -> bool:
    now = datetime.now(UTC).isoformat()
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        result = connection.execute(
            """
            UPDATE video_jobs SET video_id = ?, artifact_path = ?, updated_at = ?
            WHERE job_id = ? AND status = 'running' AND lease_owner = ?
            """,
            (video_id, artifact_path, now, job_id, worker_id),
        )
        connection.commit()
    return result.rowcount == 1


def video_job_cancel_requested(
    job_id: str,
    worker_id: str,
    *,
    database_path: Path | None = None,
) -> bool:
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        row = connection.execute(
            """
            SELECT cancel_requested_at FROM video_jobs
            WHERE job_id = ? AND status = 'running' AND lease_owner = ?
            """,
            (job_id, worker_id),
        ).fetchone()
    return row is not None and row["cancel_requested_at"] is not None


def request_video_job_cancellation(
    job_id: str,
    organization_id: str,
    project_id: str,
    *,
    database_path: Path | None = None,
) -> VideoJob | None:
    now = datetime.now(UTC).isoformat()
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM video_jobs
                WHERE job_id = ? AND organization_id = ? AND project_id = ?
                """,
                (job_id, organization_id, project_id),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            status = str(row["status"])
            if status == "queued":
                connection.execute(
                    """
                    UPDATE video_jobs
                    SET status = 'cancelled', stage = 'cancelled', cancel_requested_at = ?,
                        completed_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (now, now, now, job_id),
                )
            elif status == "running":
                connection.execute(
                    """
                    UPDATE video_jobs
                    SET cancel_requested_at = COALESCE(cancel_requested_at, ?), updated_at = ?
                    WHERE job_id = ?
                    """,
                    (now, now, job_id),
                )
            updated = connection.execute("SELECT * FROM video_jobs WHERE job_id = ?", (job_id,)).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return _job_from_row(updated) if updated is not None else None


def complete_video_job(
    job_id: str,
    worker_id: str,
    result_payload: dict[str, Any],
    *,
    database_path: Path | None = None,
) -> bool:
    now = datetime.now(UTC).isoformat()
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        result = connection.execute(
            """
            UPDATE video_jobs
            SET status = 'succeeded', stage = 'completed', progress_percent = 100,
                result_json = ?, error_code = NULL, error_message = NULL,
                completed_at = ?, updated_at = ?, lease_owner = NULL, lease_expires_at = NULL
            WHERE job_id = ? AND status = 'running' AND lease_owner = ?
              AND cancel_requested_at IS NULL
            """,
            (json.dumps(result_payload, ensure_ascii=False), now, now, job_id, worker_id),
        )
        connection.commit()
    return result.rowcount == 1


def cancel_claimed_video_job(
    job_id: str,
    worker_id: str,
    *,
    database_path: Path | None = None,
) -> bool:
    now = datetime.now(UTC).isoformat()
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        result = connection.execute(
            """
            UPDATE video_jobs
            SET status = 'cancelled', stage = 'cancelled', completed_at = ?, updated_at = ?,
                lease_owner = NULL, lease_expires_at = NULL
            WHERE job_id = ? AND status = 'running' AND lease_owner = ?
            """,
            (now, now, job_id, worker_id),
        )
        connection.commit()
    return result.rowcount == 1


def fail_video_job(
    job_id: str,
    worker_id: str,
    error_code: str,
    error_message: str,
    *,
    retryable: bool = True,
    database_path: Path | None = None,
) -> VideoJob | None:
    now = datetime.now(UTC)
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM video_jobs
                WHERE job_id = ? AND status = 'running' AND lease_owner = ?
                """,
                (job_id, worker_id),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            if row["cancel_requested_at"] is not None:
                status = "cancelled"
                stage = "cancelled"
                completed_at: str | None = now.isoformat()
                available_at = str(row["available_at"])
            elif retryable and int(row["attempts"]) < int(row["max_attempts"]):
                status = "queued"
                stage = "retry_scheduled"
                completed_at = None
                available_at = (now + timedelta(seconds=min(60, 2 ** int(row["attempts"])))).isoformat()
            else:
                status = "failed"
                stage = "failed"
                completed_at = now.isoformat()
                available_at = str(row["available_at"])
            connection.execute(
                """
                UPDATE video_jobs
                SET status = ?, stage = ?, error_code = ?, error_message = ?,
                    available_at = ?, completed_at = ?, updated_at = ?,
                    lease_owner = NULL, lease_expires_at = NULL
                WHERE job_id = ? AND status = 'running' AND lease_owner = ?
                """,
                (
                    status,
                    stage,
                    error_code[:50],
                    error_message[:300],
                    available_at,
                    completed_at,
                    now.isoformat(),
                    job_id,
                    worker_id,
                ),
            )
            updated = connection.execute("SELECT * FROM video_jobs WHERE job_id = ?", (job_id,)).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return _job_from_row(updated) if updated is not None else None


def _recover_expired_jobs(connection: sqlite3.Connection, now_iso: str) -> None:
    connection.execute(
        """
        UPDATE video_jobs
        SET status = 'cancelled', stage = 'cancelled', completed_at = ?, updated_at = ?,
            lease_owner = NULL, lease_expires_at = NULL
        WHERE status = 'running' AND lease_expires_at < ? AND cancel_requested_at IS NOT NULL
        """,
        (now_iso, now_iso, now_iso),
    )
    connection.execute(
        """
        UPDATE video_jobs
        SET status = 'failed', stage = 'failed', error_code = 'lease_expired',
            error_message = 'Video processing stopped before completion.', completed_at = ?, updated_at = ?,
            lease_owner = NULL, lease_expires_at = NULL
        WHERE status = 'running' AND lease_expires_at < ? AND attempts >= max_attempts
        """,
        (now_iso, now_iso, now_iso),
    )
    connection.execute(
        """
        UPDATE video_jobs
        SET status = 'queued', stage = 'recovered', available_at = ?, updated_at = ?,
            lease_owner = NULL, lease_expires_at = NULL
        WHERE status = 'running' AND lease_expires_at < ? AND attempts < max_attempts
          AND cancel_requested_at IS NULL
        """,
        (now_iso, now_iso, now_iso),
    )


def _job_from_row(row: sqlite3.Row) -> VideoJob:
    request_payload = cast(dict[str, Any], json.loads(str(row["request_json"])))
    result_payload = (
        cast(dict[str, Any], json.loads(str(row["result_json"])))
        if row["result_json"] is not None
        else None
    )
    return VideoJob(
        job_id=str(row["job_id"]),
        organization_id=str(row["organization_id"]),
        project_id=str(row["project_id"]),
        owner_user_id=str(row["owner_user_id"]) if row["owner_user_id"] is not None else None,
        source_kind=cast(VideoSourceKind, str(row["source_kind"])),
        status=cast(VideoJobStatus, str(row["status"])),
        stage=str(row["stage"]),
        progress_percent=int(row["progress_percent"]),
        request_payload=request_payload,
        result_payload=result_payload,
        error_code=str(row["error_code"]) if row["error_code"] is not None else None,
        error_message=str(row["error_message"]) if row["error_message"] is not None else None,
        idempotency_key=str(row["idempotency_key"]),
        video_id=str(row["video_id"]) if row["video_id"] is not None else None,
        artifact_path=str(row["artifact_path"]) if row["artifact_path"] is not None else None,
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        available_at=_parse_datetime(row["available_at"]),
        lease_owner=str(row["lease_owner"]) if row["lease_owner"] is not None else None,
        lease_expires_at=_parse_optional_datetime(row["lease_expires_at"]),
        heartbeat_at=_parse_optional_datetime(row["heartbeat_at"]),
        cancel_requested_at=_parse_optional_datetime(row["cancel_requested_at"]),
        created_at=_parse_datetime(row["created_at"]),
        started_at=_parse_optional_datetime(row["started_at"]),
        completed_at=_parse_optional_datetime(row["completed_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def _parse_datetime(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def _parse_optional_datetime(value: object) -> datetime | None:
    return _parse_datetime(value) if value is not None else None
