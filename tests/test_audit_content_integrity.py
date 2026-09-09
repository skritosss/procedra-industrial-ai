"""The audit trail must fix the text a decision was about, not only the decision.

The chain proves the record of approvals was not rewritten. It said nothing
about the instruction those approvals covered, and `instruction_versions` has no
immutability triggers — a direct edit of `payload_json` passed both checks.
"""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.auth_store import create_user
from app.storage.database import reset_schema_cache, verify_database


REQUEST = {
    "task": "Подготовка рабочего места оператора пресса",
    "industry_profile": "manufacturing",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name, value in {
        "DATABASE_PATH": str(tmp_path / "a.db"),
        "METRICS_DATABASE_PATH": str(tmp_path / "m.db"),
        "RATE_LIMIT_DATABASE_PATH": str(tmp_path / "r.db"),
        "RATE_LIMIT_ENABLED": "false",
    }.items():
        monkeypatch.setenv(name, value)
    from app.core.settings import get_settings

    get_settings.cache_clear()
    reset_schema_cache()
    with TestClient(app) as instance:
        yield instance
    get_settings.cache_clear()
    reset_schema_cache()


def _save_version(client) -> tuple[str, int]:
    payload = client.post("/api/instructions/generate-with-context", json=REQUEST).json()
    record = client.post("/api/instructions/history", json={"payload": payload}).json()["record"]
    return record["instruction_id"], record["version"]


def test_editing_a_stored_version_breaks_verification(client, tmp_path) -> None:
    _save_version(client)
    database_path = tmp_path / "a.db"

    reset_schema_cache()
    verify_database(database_path)  # clean before the edit

    with sqlite3.connect(database_path) as connection:
        changed = connection.execute(
            "UPDATE instruction_versions SET payload_json = replace(payload_json, 'оператора', 'ОПЕРАТОРА')"
        ).rowcount
    assert changed, "правка не применилась — тест ничего не проверяет"

    reset_schema_cache()
    with pytest.raises(ValueError, match="does not match its audit trail"):
        verify_database(database_path)


def test_a_workflow_decision_does_not_look_like_tampering(client, tmp_path) -> None:
    """The payload legitimately changes when a reviewer records a decision. If
    the digest were frozen at save time, ordinary use would report tampering."""
    instruction_id, version = _save_version(client)

    response = client.patch(
        f"/api/instructions/history/{instruction_id}/versions/{version}/workflow",
        json={
            "status": "expert_review",
            "reviewer": "Иванов Иван",
            "reviewer_role": "technologist",
            "comment": "Передано технологу на проверку",
        },
    )
    assert response.status_code == 200

    reset_schema_cache()
    verify_database(tmp_path / "a.db")

    with sqlite3.connect(tmp_path / "a.db") as connection:
        events = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT event_json FROM instruction_audit_events ORDER BY sequence"
            )
        ]
    digests = [event["metadata"]["content_sha256"] for event in events]
    assert len(digests) == 2
    # Each event fixes the text as of itself, which is why the second differs.
    assert digests[0] != digests[1]


def test_confirming_a_claim_does_not_look_like_tampering(client, tmp_path) -> None:
    create_user(
        "tech@example.com",
        "Иванов Иван",
        "strong-password-1",
        role="technologist",
        database_path=tmp_path / "a.db",
    )
    login = client.post(
        "/api/auth/login", json={"email": "tech@example.com", "password": "strong-password-1"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    payload = client.post("/api/instructions/generate-with-context", headers=headers, json=REQUEST).json()
    record = client.post("/api/instructions/history", headers=headers, json={"payload": payload}).json()["record"]
    claim_id = payload["instruction"]["evidence_claims"][0]["claim_id"]

    response = client.post(
        f"/api/instructions/history/{record['instruction_id']}/versions/{record['version']}"
        f"/claims/{claim_id}/validate",
        headers=headers,
        json={
            "evidence_reference": "Технологическая карта 12-45",
            "evidence_sha256": "a" * 64,
            "comment": "Сверено с технологической картой участка",
        },
    )
    assert response.status_code == 200

    reset_schema_cache()
    verify_database(tmp_path / "a.db")
