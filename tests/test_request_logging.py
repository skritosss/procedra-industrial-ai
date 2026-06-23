import json
import logging
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from app.core.request_logging import REQUEST_LOGGER, RequestJsonFormatter
from app.main import app
from app.storage.auth_store import create_session, create_user


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []
        self.setFormatter(RequestJsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


def test_request_log_contains_safe_authenticated_context() -> None:
    user = create_user("logger@example.com", "Logger User", "strong-password-1")
    token = create_session(user.user_id)
    handler = _ListHandler()
    original_handlers = list(REQUEST_LOGGER.handlers)
    REQUEST_LOGGER.handlers[:] = [handler]
    setattr(REQUEST_LOGGER, "_industrial_ai_configured_pid", __import__("os").getpid())
    try:
        response = TestClient(app).get(
            "/api/auth/me?email=private@example.com&access_token=never-log-this",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": "request-log-1",
                "Cookie": "session=never-log-this",
            },
        )
    finally:
        REQUEST_LOGGER.handlers[:] = original_handlers

    assert response.status_code == 200
    assert len(handler.messages) == 1
    payload = json.loads(handler.messages[-1])
    assert payload["request_id"] == "request-log-1"
    assert payload["actor_id"] == user.user_id
    assert payload["organization_id"] == user.organization_id
    assert payload["project_id"] == user.project_id
    assert payload["route_template"] == "/api/auth/me"
    assert payload["status"] == 200
    assert payload["result_category"] == "success"
    assert payload["error_category"] is None
    serialized = handler.messages[-1]
    assert token not in serialized
    assert "private@example.com" not in serialized
    assert "never-log-this" not in serialized


def test_request_log_uses_safe_error_categories_and_never_logs_credentials() -> None:
    handler = _ListHandler()
    original_handlers = list(REQUEST_LOGGER.handlers)
    REQUEST_LOGGER.handlers[:] = [handler]
    setattr(REQUEST_LOGGER, "_industrial_ai_configured_pid", __import__("os").getpid())
    try:
        response = TestClient(app).post(
            "/api/auth/login",
            headers={"X-Request-ID": "Bearer secret-value"},
            json={"email": "person@example.com", "password": "top-secret-password"},
        )
    finally:
        REQUEST_LOGGER.handlers[:] = original_handlers

    assert response.status_code == 401
    assert len(handler.messages) == 1
    payload = json.loads(handler.messages[-1])
    assert payload["request_id"] == "[redacted]"
    assert payload["route_template"] == "/api/auth/login"
    assert payload["result_category"] == "security_denied"
    assert payload["error_category"] == "unauthorized"
    assert "person@example.com" not in handler.messages[-1]
    assert "top-secret-password" not in handler.messages[-1]
    assert "secret-value" not in handler.messages[-1]


def test_formatter_whitelists_fields_and_redacts_pii() -> None:
    formatter = RequestJsonFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "ignored", (), None)
    record.request_event = {
        "request_id": "person@example.com",
        "actor_id": "actor-1",
        "organization_id": "org-1",
        "project_id": "project-1",
        "method": "POST",
        "route_template": "/api/items/{item_id}",
        "duration_ms": 12.34567,
        "status": 422,
        "result_category": "client_error",
        "error_category": "validation_error",
        "authorization": "Bearer secret-token",
        "request_body": {"password": "secret"},
    }

    serialized = formatter.format(record)
    payload = json.loads(serialized)

    assert payload["request_id"] == "[redacted]"
    assert payload["duration_ms"] == 12.346
    assert set(payload) == {
        "timestamp",
        "schema_version",
        "service",
        "event",
        "worker_pid",
        "request_id",
        "actor_id",
        "organization_id",
        "project_id",
        "method",
        "route_template",
        "duration_ms",
        "status",
        "result_category",
        "error_category",
    }
    assert "secret-token" not in serialized
    assert "password" not in serialized


def test_independent_workers_emit_complete_json_records(tmp_path: Path) -> None:
    script = """
import logging
from app.core.request_logging import REQUEST_LOGGER, configure_request_logging
configure_request_logging()
for index in range(25):
    REQUEST_LOGGER.info('http_request', extra={'request_event': {
        'request_id': f'worker-{index}', 'actor_id': 'actor-1',
        'organization_id': 'org-1', 'project_id': 'project-1',
        'method': 'GET', 'route_template': '/health', 'duration_ms': index,
        'status': 200, 'result_category': 'success', 'error_category': None,
    }})
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(3)
    ]
    records: list[dict] = []
    for process in processes:
        _, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        records.extend(json.loads(line) for line in stderr.splitlines() if line.strip())

    assert len(records) == 75
    assert len({record["worker_pid"] for record in records}) == 3
    assert all(record["event"] == "http_request" for record in records)
    assert all(record["route_template"] == "/health" for record in records)
