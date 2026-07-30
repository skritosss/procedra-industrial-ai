from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.authorization import get_resource_ownership
from app.core.settings import get_settings
from app.main import app
from app.schemas.video import VideoKeyframeResponse
from app.storage.video_jobs import (
    cancel_claimed_video_job,
    claim_next_video_job,
    create_video_job,
    fail_video_job,
    get_video_job,
    request_video_job_cancellation,
)
from app.workers import video_jobs as video_worker
from app.workers.stage_process import StageInterruptedError, StageTimeoutError


def _create_url_job(idempotency_key: str = "durable-video-job"):
    settings = get_settings()
    return create_video_job(
        "legacy",
        "legacy",
        None,
        "url",
        {"video_url": "https://example.com/video", "visual_quality": "720", "max_keyframes": 4},
        idempotency_key,
        database_path=settings.database_path,
    )[0]


def test_video_job_api_is_idempotent_and_cancels_queued_upload() -> None:
    client = TestClient(app)
    headers = {"Idempotency-Key": "same-upload-request-001"}

    first = client.post(
        "/api/videos/jobs",
        headers=headers,
        data={"max_keyframes": "4"},
        files={"file": ("sample.mp4", b"video bytes", "video/mp4")},
    )
    second = client.post(
        "/api/videos/jobs",
        headers=headers,
        data={"max_keyframes": "4"},
        files={"file": ("sample.mp4", b"different bytes", "video/mp4")},
    )

    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert "video_url" not in first.json()

    cancelled = client.delete(f"/api/videos/jobs/{first.json()['job_id']}")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/api/videos/jobs/{first.json()['job_id']}/result").status_code == 409


def test_concurrent_idempotent_enqueue_creates_one_job() -> None:
    settings = get_settings()

    def enqueue(_index: int):
        return create_video_job(
            "legacy",
            "legacy",
            None,
            "url",
            {"video_url": "https://example.com/video", "visual_quality": "720", "max_keyframes": 4},
            "concurrent-idempotency-key",
            database_path=settings.database_path,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(enqueue, range(8)))

    assert len({job.job_id for job, _created in results}) == 1
    assert sum(1 for _job, created in results if created) == 1


def test_video_job_worker_completes_upload_and_exposes_result(monkeypatch) -> None:
    client = TestClient(app)
    queued = client.post(
        "/api/videos/jobs",
        headers={"Idempotency-Key": "worker-success-upload"},
        data={"max_keyframes": "4"},
        files={"file": ("sample.mp4", b"video bytes", "video/mp4")},
    )
    job_id = queued.json()["job_id"]
    def extract(**kwargs):
        return VideoKeyframeResponse(
            video_id=kwargs["video_id"],
            original_filename=kwargs["original_filename"],
            frame_count=1,
            fps=1,
            duration_seconds=1,
            keyframes=[],
            visual_quality="uploaded",
        )

    def run_stage(stage, payload, **_kwargs):
        if stage == "extract":
            return extract(**payload).model_dump(mode="json")
        if stage == "analyze":
            return payload["response"]
        raise AssertionError(f"Unexpected stage: {stage}")

    monkeypatch.setattr(video_worker, "_run_stage", run_stage)

    assert video_worker.run_one_video_job("test-worker", settings=get_settings()) is True
    status = client.get(f"/api/videos/jobs/{job_id}")
    result = client.get(f"/api/videos/jobs/{job_id}/result")

    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"
    assert status.json()["progress_percent"] == 100
    assert result.status_code == 200
    video_id = result.json()["video_id"]
    assert get_resource_ownership(
        "legacy",
        "video",
        video_id,
        database_path=get_settings().database_path,
    ) is not None


def test_expired_worker_lease_recovers_job_without_duplication() -> None:
    job = _create_url_job("lease-recovery-job")
    start = datetime.now(UTC) + timedelta(seconds=1)
    first = claim_next_video_job(
        "worker-a",
        lease_seconds=30,
        database_path=get_settings().database_path,
        now=start,
    )
    recovered = claim_next_video_job(
        "worker-b",
        lease_seconds=30,
        database_path=get_settings().database_path,
        now=start + timedelta(seconds=31),
    )

    assert first is not None and first.job_id == job.job_id and first.attempts == 1
    assert recovered is not None and recovered.job_id == job.job_id
    assert recovered.attempts == 2
    assert recovered.lease_owner == "worker-b"


def test_running_job_cancellation_is_cooperative() -> None:
    job = _create_url_job("running-cancel-job")
    claimed = claim_next_video_job(
        "worker-a",
        lease_seconds=30,
        database_path=get_settings().database_path,
    )
    assert claimed is not None

    requested = request_video_job_cancellation(
        job.job_id,
        "legacy",
        "legacy",
        database_path=get_settings().database_path,
    )
    assert requested is not None
    assert requested.status == "running"
    assert requested.cancel_requested is True
    assert cancel_claimed_video_job(
        job.job_id,
        "worker-a",
        database_path=get_settings().database_path,
    )
    assert get_video_job(
        job.job_id,
        "legacy",
        "legacy",
        database_path=get_settings().database_path,
    ).status == "cancelled"


def test_worker_discards_result_when_cancel_arrives_during_processing(monkeypatch) -> None:
    client = TestClient(app)
    queued = client.post(
        "/api/videos/jobs",
        headers={"Idempotency-Key": "cancel-during-processing"},
        data={"max_keyframes": "4"},
        files={"file": ("sample.mp4", b"video bytes", "video/mp4")},
    )
    job_id = queued.json()["job_id"]

    def run_stage(stage, payload, **_kwargs):
        if stage == "extract":
            request_video_job_cancellation(
                job_id,
                "legacy",
                "legacy",
                database_path=get_settings().database_path,
            )
            reason = _kwargs["interrupt_reason"]()
            raise StageInterruptedError(stage, reason or "missing_reason")
        if stage == "analyze":
            return payload["response"]
        raise AssertionError(f"Unexpected stage: {stage}")

    monkeypatch.setattr(video_worker, "_run_stage", run_stage)

    assert video_worker.run_one_video_job("cancel-worker", settings=get_settings()) is True
    final = client.get(f"/api/videos/jobs/{job_id}").json()
    assert final["status"] == "cancelled"
    assert final["result_available"] is False


def test_worker_stage_timeout_uses_retry_budget_and_public_error(monkeypatch) -> None:
    settings = get_settings().model_copy(update={"video_job_max_attempts": 1})
    monkeypatch.setattr("app.api.videos.get_settings", lambda: settings)
    client = TestClient(app)
    queued = client.post(
        "/api/videos/jobs",
        headers={"Idempotency-Key": "extract-timeout-public-error"},
        data={"max_keyframes": "4"},
        files={"file": ("sample.mp4", b"video bytes", "video/mp4")},
    )
    job_id = queued.json()["job_id"]
    stored_before = get_video_job(
        job_id,
        "legacy",
        "legacy",
        database_path=settings.database_path,
    )
    assert stored_before is not None
    assert stored_before.artifact_path is not None
    assert Path(stored_before.artifact_path).exists()

    def run_stage(stage, _payload, **_kwargs):
        raise StageTimeoutError(stage)

    monkeypatch.setattr(video_worker, "_run_stage", run_stage)

    assert video_worker.run_one_video_job("timeout-worker", settings=settings) is True
    final = client.get(f"/api/videos/jobs/{job_id}").json()

    assert final["status"] == "failed"
    assert final["attempts"] == 1
    assert final["error_code"] == "processing_timeout"
    assert final["error_message"] == "Video processing exceeded the configured time limit."
    assert final["result_available"] is False
    assert not Path(stored_before.artifact_path).exists()


def test_retryable_failure_requeues_until_attempt_budget_is_exhausted() -> None:
    job = _create_url_job("retry-budget-job")
    first = claim_next_video_job(
        "worker-a",
        lease_seconds=30,
        database_path=get_settings().database_path,
    )
    assert first is not None
    retried = fail_video_job(
        job.job_id,
        "worker-a",
        "download_failed",
        "The video could not be downloaded from the permitted URL.",
        retryable=True,
        database_path=get_settings().database_path,
    )
    assert retried is not None
    assert retried.status == "queued"
    assert retried.attempts == 1


def test_job_scope_hides_other_projects_and_tenants(tmp_path, monkeypatch) -> None:
    from app.core.authorization import create_project
    from app.storage.auth_store import create_organization, create_session, create_user

    database_path = tmp_path / "tenant-jobs.sqlite3"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "database_path": database_path,
            "api_access_token": "video-job-bootstrap-token-32-chars",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "video_allowed_hosts": ("example.com",),
        }
    )
    for target in (
        "app.api.videos.get_settings",
        "app.core.security.get_settings",
        "app.storage.auth_store.get_settings",
    ):
        monkeypatch.setattr(target, lambda: settings)
    organization_a = create_organization("Video Jobs A", database_path=database_path)
    organization_b = create_organization("Video Jobs B", database_path=database_path)
    user_a = create_user(
        "jobs-a@example.com",
        "Jobs A",
        "strong-production-password-a",
        organization_id=organization_a,
        database_path=database_path,
    )
    user_b = create_user(
        "jobs-b@example.com",
        "Jobs B",
        "strong-production-password-b",
        organization_id=organization_b,
        database_path=database_path,
    )
    project_a = create_project(organization_a, "A project", user_a.user_id, database_path=database_path)
    job = create_video_job(
        organization_a,
        project_a,
        user_a.user_id,
        "url",
        {"video_url": "https://example.com/video", "visual_quality": "720", "max_keyframes": 4},
        "tenant-isolation-job",
        database_path=database_path,
    )[0]
    token_a = create_session(user_a.user_id, database_path=database_path)
    token_b = create_session(user_b.user_id, database_path=database_path)
    client = TestClient(app)

    assert client.get(
        f"/api/videos/jobs/{job.job_id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Project-ID": project_a},
    ).status_code == 200
    assert client.get(
        f"/api/videos/jobs/{job.job_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    ).status_code == 404
