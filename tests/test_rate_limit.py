from contextlib import closing
import sqlite3
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core import rate_limit
from app.core.rate_limit import reset_rate_limit_state
from app.core.settings import get_settings
from app.main import app


def _consume_in_process(database_path: str) -> str:
    return rate_limit._consume_bucket(
        Path(database_path),
        "shared-process-bucket",
        limit=3,
        window_seconds=60,
        cleanup_window_seconds=300,
        now=1_000.0,
    ).status


def test_shared_backend_is_atomic_across_threads(tmp_path) -> None:
    database_path = tmp_path / "thread-rate-limit.sqlite3"

    def consume(_: int) -> str:
        return rate_limit._consume_bucket(
            database_path,
            "shared-thread-bucket",
            limit=5,
            window_seconds=60,
            cleanup_window_seconds=300,
            now=1_000.0,
        ).status

    with ThreadPoolExecutor(max_workers=10) as executor:
        statuses = list(executor.map(consume, range(10)))
    assert statuses.count("allowed") == 5
    assert statuses.count("limited") == 5


def test_shared_backend_is_atomic_across_worker_processes(tmp_path) -> None:
    database_path = tmp_path / "process-rate-limit.sqlite3"
    try:
        with ProcessPoolExecutor(max_workers=4) as executor:
            statuses = list(executor.map(_consume_in_process, [str(database_path)] * 6))
    except (NotImplementedError, PermissionError) as exc:
        pytest.skip(f"Process pools are unavailable in this sandbox: {exc}")
    assert statuses.count("allowed") == 3
    assert statuses.count("limited") == 3


def test_shared_backend_survives_process_local_state_reset(tmp_path) -> None:
    database_path = tmp_path / "restart-rate-limit.sqlite3"
    first = rate_limit._consume_bucket(
        database_path,
        "restart-bucket",
        limit=1,
        window_seconds=60,
        cleanup_window_seconds=300,
        now=1_000.0,
    )
    second = rate_limit._consume_bucket(
        database_path,
        "restart-bucket",
        limit=1,
        window_seconds=60,
        cleanup_window_seconds=300,
        now=1_001.0,
    )
    assert first.status == "allowed"
    assert second.status == "limited"
    assert second.retry_after_seconds == 59


def test_rate_limit_storage_failure_fails_closed_only_for_protected_routes(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={
            "rate_limit_database_path": tmp_path / "unavailable.sqlite3",
            "rate_limit_enabled": True,
        }
    )
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.core.rate_limit.connect_rate_limit_store",
        lambda *_: (_ for _ in ()).throw(sqlite3.OperationalError("storage unavailable")),
    )
    client = TestClient(app)

    protected = client.post("/api/auth/login", json={"email": "missing@example.com", "password": "wrong"})
    health = client.get("/health")

    assert protected.status_code == 503
    assert protected.json()["error"]["code"] == "rate_limit_unavailable"
    assert health.status_code == 200


def test_dynamic_expensive_paths_share_one_bounded_bucket(monkeypatch) -> None:
    settings = get_settings().model_copy(update={"trusted_proxy_ips": (), "trust_proxy_headers": False})
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    from starlette.requests import Request

    first = Request({"type": "http", "method": "POST", "path": "/api/videos/one", "headers": [], "client": ("127.0.0.1", 1)})
    second = Request({"type": "http", "method": "POST", "path": "/api/videos/two", "headers": [], "client": ("127.0.0.1", 2)})
    assert rate_limit._bucket_hash(rate_limit._client_key(first)) == rate_limit._bucket_hash(rate_limit._client_key(second))


def test_authenticated_users_behind_one_address_receive_separate_buckets(monkeypatch) -> None:
    settings = get_settings().model_copy(update={"trusted_proxy_ips": (), "trust_proxy_headers": False})
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    from starlette.requests import Request

    first = Request({"type": "http", "method": "POST", "path": "/api/documents/upload", "headers": [], "client": ("127.0.0.1", 1)})
    second = Request({"type": "http", "method": "POST", "path": "/api/documents/upload", "headers": [], "client": ("127.0.0.1", 2)})
    first.state.current_user = SimpleNamespace(user_id="user-a")
    second.state.current_user = SimpleNamespace(user_id="user-b")
    assert rate_limit._client_key(first) != rate_limit._client_key(second)


def test_rate_limit_events_do_not_touch_the_business_database(tmp_path, monkeypatch) -> None:
    business = tmp_path / "business.sqlite3"
    limits = tmp_path / "limits.sqlite3"
    settings = get_settings().model_copy(
        update={
            "database_path": business,
            "rate_limit_database_path": limits,
            "rate_limit_enabled": True,
        }
    )
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    reset_rate_limit_state(limits)
    client = TestClient(app)

    client.post("/api/auth/login", json={"email": "missing@example.com", "password": "wrong"})

    # The metrics store was split out to stop sharing the single SQLite writer;
    # the limiter had been left behind in the business database.
    with closing(sqlite3.connect(limits)) as connection:
        recorded = connection.execute("SELECT COUNT(*) FROM rate_limit_events").fetchone()[0]
    assert recorded >= 1

    with closing(sqlite3.connect(business)) as connection:
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert "rate_limit_events" not in tables
