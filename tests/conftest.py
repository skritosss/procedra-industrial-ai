from pathlib import Path

import pytest

from app.core.rate_limit import reset_rate_limit_state
from app.core.settings import get_settings
from app.storage.database import reset_schema_cache
from app.storage.metrics_store import initialize_metrics_store


@pytest.fixture(autouse=True)
def isolate_runtime_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runtime_root = tmp_path / "runtime"
    database_path = runtime_root / "app.sqlite3"
    metrics_database_path = runtime_root / "metrics.sqlite3"
    documents_path = runtime_root / "uploads" / "documents"
    keyframes_path = runtime_root / "generated" / "keyframes"
    videos_path = runtime_root / "uploads" / "videos"
    documents_path.mkdir(parents=True)
    keyframes_path.mkdir(parents=True)
    videos_path.mkdir(parents=True)
    monkeypatch.setenv("DATABASE_PATH", str(database_path))
    monkeypatch.setenv("METRICS_DATABASE_PATH", str(metrics_database_path))
    monkeypatch.setenv("DEPLOYMENT_MODE", "demo")
    monkeypatch.setenv("OPENAI_ENABLED", "false")
    monkeypatch.setenv("API_ACCESS_TOKEN", "")
    # An empty token no longer implies open access, so the suite has to ask for
    # it the same way an operator would.
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED_ACCESS", "true")
    monkeypatch.setenv("AUTH_PUBLIC_REGISTRATION_ENABLED", "true")
    monkeypatch.setenv("AUTH_ALLOW_ROLE_SELF_ASSIGNMENT", "true")
    get_settings.cache_clear()
    # Each test gets fresh database files and a path can repeat across runs, so
    # the per-process schema cache must not carry over between tests.
    reset_schema_cache()
    reset_rate_limit_state(database_path)
    initialize_metrics_store(metrics_database_path)

    monkeypatch.setattr("app.api.documents.UPLOADED_DOCUMENTS_DIR", documents_path)
    monkeypatch.setattr("app.api.instructions.UPLOADED_KNOWLEDGE_BASE", documents_path)
    monkeypatch.setattr("app.main.KEYFRAMES_DIR", keyframes_path)
    monkeypatch.setattr("app.vision.keyframes.KEYFRAME_DIR", keyframes_path)
    monkeypatch.setattr("app.vision.keyframes.UPLOAD_DIR", videos_path)
    monkeypatch.setattr("app.vision.keyframes.PROJECT_ROOT", runtime_root)

    yield
    get_settings.cache_clear()
    # Each test gets fresh database files and a path can repeat across runs, so
    # the per-process schema cache must not carry over between tests.
    reset_schema_cache()
