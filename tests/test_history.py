import pytest
from fastapi.testclient import TestClient
from datetime import UTC, datetime, timedelta

from app.main import app
from app.core.settings import get_settings
from app.schemas.instruction import InstructionRequest
from app.generation.pipeline import generate_instruction
from app.storage import instruction_history
from app.storage.instruction_history import (
    HISTORY_DATABASE_FILENAME,
    get_instruction_history_detail,
    save_instruction_history,
)
from app.storage.auth_store import create_organization, create_session, create_user


def test_instruction_history_save_list_and_get(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)

    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить аварийную кнопку станка перед запуском смены",
            "equipment": "Ленточнопильный станок",
            "instruction_type": "inspection",
        },
    )
    assert generated.status_code == 200
    payload = generated.json()

    first = client.post("/api/instructions/history", json={"payload": payload})
    second = client.post("/api/instructions/history", json={"payload": payload})

    assert first.status_code == 200
    assert second.status_code == 200
    first_record = first.json()["record"]
    second_record = second.json()["record"]
    assert first_record["version"] == 1
    assert second_record["version"] == 2
    assert first_record["instruction_id"] == second_record["instruction_id"]

    list_response = client.get("/api/instructions/history")
    assert list_response.status_code == 200
    records = list_response.json()["records"]
    assert len(records) == 2
    assert records[0]["version"] == 2

    detail = client.get(
        f"/api/instructions/history/{first_record['instruction_id']}/versions/1"
    )
    assert detail.status_code == 200
    assert detail.json()["payload"]["instruction"]["title"] == payload["instruction"]["title"]


def test_instruction_history_returns_404_for_missing_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)

    response = client.get("/api/instructions/history/missing/versions/1")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_instruction_history_rejects_unsafe_id(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)

    response = client.get("/api/instructions/history/..%2Fsecret/versions/1")

    assert response.status_code == 404


def test_instruction_history_list_sorts_by_created_at_before_limit(tmp_path) -> None:
    older = {
        "record": {
            "instruction_id": "older",
            "version": 1,
            "title": "Older",
            "created_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "generation_mode": "fallback",
            "overall_score": 90,
            "risk_level": "low",
            "workflow_status": "ai_draft",
            "workflow_status_label": "AI-черновик",
            "source_count": 0,
            "step_count": 1,
        },
        "payload": _minimal_history_payload("Older"),
    }
    newer = {
        "record": {
            "instruction_id": "newer",
            "version": 1,
            "title": "Newer",
            "created_at": datetime.now(UTC).isoformat(),
            "generation_mode": "fallback",
            "overall_score": 90,
            "risk_level": "low",
            "workflow_status": "ai_draft",
            "workflow_status_label": "AI-черновик",
            "source_count": 0,
            "step_count": 1,
        },
        "payload": _minimal_history_payload("Newer"),
    }
    import json

    (tmp_path / "z-older-v1.json").write_text(json.dumps(older), encoding="utf-8")
    (tmp_path / "a-newer-v1.json").write_text(json.dumps(newer), encoding="utf-8")

    records = instruction_history.list_instruction_history(history_dir=tmp_path, limit=1)

    assert records[0].instruction_id == "newer"


def test_instruction_history_updates_workflow_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить защитное ограждение станка перед запуском смены",
            "equipment": "Ленточнопильный станок",
            "instruction_type": "inspection",
        },
    )
    payload = generated.json()
    saved = client.post("/api/instructions/history", json={"payload": payload}).json()["record"]

    review = client.patch(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow",
        json={
            "status": "expert_review",
            "reviewer": "Мастер смены",
            "reviewer_role": "master",
            "comment": "Передано на проверку мастеру и специалисту по охране труда.",
        },
    )

    assert review.status_code == 200
    reviewed_record = review.json()["record"]
    assert reviewed_record["workflow_status"] == "expert_review"
    assert reviewed_record["workflow_status_label"] == "На экспертной проверке"
    assert reviewed_record["reviewer"] == "Мастер смены"
    assert reviewed_record["reviewer_role"] == "master"
    assert reviewed_record["review_comment"]
    assert reviewed_record["reviewed_at"]

    detail = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
    ).json()
    assert detail["payload"]["instruction"]["workflow"]["status"] == "expert_review"
    assert "Мастер смены" in " ".join(detail["payload"]["instruction"]["workflow"]["next_actions"])
    audit = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/audit"
    )
    assert audit.status_code == 200
    events = audit.json()["events"]
    assert [event["event_type"] for event in events] == ["version_saved", "workflow_updated"]
    assert events[1]["actor"] == "Мастер смены"
    assert events[1]["reviewer_role"] == "master"
    assert events[1]["from_status"] == "ai_draft"
    assert events[1]["to_status"] == "expert_review"


def test_instruction_history_approval_marks_blockers_as_resolved(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить аварийную остановку оборудования перед запуском",
            "equipment": "Производственное оборудование",
            "instruction_type": "inspection",
        },
    )
    saved = client.post("/api/instructions/history", json={"payload": generated.json()}).json()["record"]
    review = client.patch(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow",
        json={
            "status": "expert_review",
            "reviewer": "Мастер смены",
            "reviewer_role": "master",
            "comment": "Передано на экспертную проверку перед утверждением.",
        },
    )
    assert review.status_code == 200

    approved = client.patch(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow",
        json={
            "status": "approved",
            "reviewer": "Инженер по охране труда",
            "reviewer_role": "safety",
            "comment": "Локальные параметры проверены, инструкция разрешена для пилотного применения.",
            "resolved_blockers": ["Не подтверждены локальные режимы"],
        },
    )

    assert approved.status_code == 200
    assert approved.json()["record"]["workflow_status"] == "approved"
    detail = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
    ).json()
    assert detail["payload"]["instruction"]["workflow"]["status_label"] == "Утверждено"
    assert "Блокеры утверждения закрыты" in detail["payload"]["instruction"]["workflow"]["approval_blockers"][0]


def test_instruction_history_rejects_direct_draft_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить аварийную остановку оборудования перед запуском",
            "equipment": "Производственное оборудование",
            "instruction_type": "inspection",
        },
    )
    saved = client.post("/api/instructions/history", json={"payload": generated.json()}).json()["record"]

    response = client.patch(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow",
        json={
            "status": "approved",
            "reviewer": "Инженер по охране труда",
            "reviewer_role": "safety",
            "comment": "Пытаемся утвердить без экспертной проверки.",
        },
    )

    assert response.status_code == 400
    assert "Invalid workflow transition" in response.json()["error"]["message"]


def test_instruction_history_rejects_approval_by_non_approval_role(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить аварийную остановку оборудования перед запуском",
            "equipment": "Производственное оборудование",
            "instruction_type": "inspection",
        },
    )
    saved = client.post("/api/instructions/history", json={"payload": generated.json()}).json()["record"]
    review = client.patch(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow",
        json={
            "status": "expert_review",
            "reviewer": "Мастер смены",
            "reviewer_role": "master",
            "comment": "Передано на экспертную проверку перед утверждением.",
        },
    )
    assert review.status_code == 200

    approved = client.patch(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow",
        json={
            "status": "approved",
            "reviewer": "Мастер смены",
            "reviewer_role": "master",
            "comment": "Мастер пытается утвердить финальную версию.",
        },
    )

    assert approved.status_code == 400
    assert "Only technologist, safety, quality, or admin roles" in approved.json()["error"]["message"]


def test_instruction_execution_run_is_saved_for_history_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить аварийную остановку оборудования перед запуском",
            "equipment": "Производственное оборудование",
            "instruction_type": "inspection",
        },
    )
    saved = client.post("/api/instructions/history", json={"payload": generated.json()}).json()["record"]
    detail = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
    ).json()
    saved_steps = [
        {
            "label": f"{step['number']}. {step['action']}",
            "completed": index == 0,
        }
        for index, step in enumerate(detail["payload"]["instruction"]["steps"])
    ]
    saved_quality_items = [
        {
            "label": detail["payload"]["instruction"]["control_points"][0],
            "completed": True,
        }
    ]

    execution = client.post(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/execution",
        json={
            "executor": "Оператор Иванов",
            "notes": "Пробный проход выполнен, замечаний по шагам нет.",
            "steps": saved_steps,
            "quality_items": saved_quality_items,
        },
    )

    assert execution.status_code == 200
    record = execution.json()["record"]
    assert record["executor"] == "Оператор Иванов"
    assert record["completed_steps"] == 1
    assert record["total_steps"] == len(saved_steps)
    assert record["completed_quality_items"] == 1

    listed = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/execution"
    )

    assert listed.status_code == 200
    assert listed.json()["records"][0]["run_id"] == record["run_id"]
    audit = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/audit"
    )
    assert audit.status_code == 200
    events = audit.json()["events"]
    assert [event["event_type"] for event in events] == ["version_saved", "execution_saved"]
    assert events[1]["actor"] == "Оператор Иванов"
    assert events[1]["metadata"]["run_id"] == record["run_id"]
    assert events[1]["metadata"]["completed_steps"] == 1

    summary = client.get("/api/instructions/history/execution-summary")

    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["total_runs"] == 1
    assert summary_payload["completed_steps"] == 1
    assert summary_payload["total_steps"] == len(saved_steps)
    assert summary_payload["step_completion_rate"] == round(100 / len(saved_steps), 1)
    assert summary_payload["latest_runs"][0]["run_id"] == record["run_id"]


def test_instruction_execution_rejects_steps_that_do_not_match_saved_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить аварийную остановку оборудования перед запуском",
            "equipment": "Производственное оборудование",
            "instruction_type": "inspection",
        },
    )
    saved = client.post("/api/instructions/history", json={"payload": generated.json()}).json()["record"]

    execution = client.post(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/execution",
        json={
            "executor": "Оператор Иванов",
            "notes": "Пробный проход содержит чужой шаг.",
            "steps": [{"label": "1. Чужой шаг из другой инструкции", "completed": True}],
        },
    )

    assert execution.status_code == 400
    assert "must match the saved instruction version" in execution.json()["error"]["message"]


def test_instruction_execution_rejects_unknown_quality_items(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={
            "task": "Проверить аварийную остановку оборудования перед запуском",
            "equipment": "Производственное оборудование",
            "instruction_type": "inspection",
        },
    )
    saved = client.post("/api/instructions/history", json={"payload": generated.json()}).json()["record"]
    detail = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
    ).json()
    saved_steps = [
        {"label": f"{step['number']}. {step['action']}", "completed": True}
        for step in detail["payload"]["instruction"]["steps"]
    ]

    execution = client.post(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/execution",
        json={
            "executor": "Оператор Иванов",
            "notes": "Пробный проход содержит чужой пункт приемки.",
            "steps": saved_steps,
            "quality_items": [{"label": "Пункт приемки из другой инструкции", "completed": True}],
        },
    )

    assert execution.status_code == 400
    assert "quality items must match" in execution.json()["error"]["message"]


def test_instruction_history_storage_uses_safe_slug(tmp_path) -> None:
    from app.generation.fallback import generate_fallback_instruction
    from app.generation.markdown import render_instruction_markdown
    from app.evaluation.quality import evaluate_instruction
    from app.schemas.instruction import InstructionResponse

    request = InstructionRequest(task="Проверить станок перед запуском смены")
    instruction = generate_fallback_instruction(request)
    instruction.title = "../../Проверить станок"
    payload = InstructionResponse(
        instruction=instruction,
        markdown=render_instruction_markdown(instruction),
        generation_mode="fallback",
        evaluation=evaluate_instruction(instruction, request),
    )

    record = instruction_history.save_instruction_history(payload, history_dir=tmp_path)

    assert "/" not in record.instruction_id
    assert "\\" not in record.instruction_id
    assert ".." not in record.instruction_id
    assert (tmp_path / instruction_history.HISTORY_DATABASE_FILENAME).is_file()


def test_instruction_audit_endpoint_returns_404_for_missing_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", tmp_path)
    client = TestClient(app)

    response = client.get("/api/instructions/history/missing/versions/1/audit")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_operator_account_cannot_update_instruction_workflow(tmp_path, monkeypatch) -> None:
    history_path = tmp_path / "history"
    settings = get_settings().model_copy(
        update={
            "api_access_token": "static-token",
            "database_path": history_path / instruction_history.HISTORY_DATABASE_FILENAME,
        }
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    auth = client.post(
        "/api/auth/register",
        json={
            "email": "operator-workflow@example.com",
            "full_name": "Оператор Петров",
            "password": "strong-password-1",
            "role": "operator",
        },
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    generated = client.post(
        "/api/instructions/generate",
        headers=headers,
        json={"task": "Проверить ограждение перед запуском оборудования"},
    ).json()
    saved = client.post("/api/instructions/history", headers=headers, json={"payload": generated}).json()["record"]

    response = client.patch(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow",
        headers=headers,
        json={
            "status": "expert_review",
            "reviewer": "Поддельный мастер",
            "reviewer_role": "master",
            "comment": "Оператор пытается изменить статус инструкции.",
        },
    )

    assert response.status_code == 403
    assert "workflow:review" in response.json()["error"]["message"]


def test_production_static_token_cannot_impersonate_lifecycle_actor(tmp_path, monkeypatch) -> None:
    history_path = tmp_path / "history"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "bootstrap-token",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "database_path": history_path / instruction_history.HISTORY_DATABASE_FILENAME,
        }
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    client = TestClient(app)
    headers = {"Authorization": "Bearer bootstrap-token"}
    generated = client.post(
        "/api/instructions/generate",
        headers=headers,
        json={"task": "Проверить рабочее место перед запуском оборудования"},
    ).json()

    response = client.post("/api/instructions/history", headers=headers, json={"payload": generated})

    assert response.status_code == 401
    assert "Authenticated user session" in response.json()["error"]["message"]


def test_authenticated_reviewer_identity_overrides_request_body(tmp_path, monkeypatch) -> None:
    history_path = tmp_path / "history"
    settings = get_settings().model_copy(
        update={
            "api_access_token": "static-token",
            "database_path": history_path / instruction_history.HISTORY_DATABASE_FILENAME,
        }
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    auth = client.post(
        "/api/auth/register",
        json={
            "email": "safety-review@example.com",
            "full_name": "Инженер Смирнова",
            "password": "strong-password-1",
            "role": "safety",
        },
    ).json()
    user = auth["user"]
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    generated = client.post(
        "/api/instructions/generate",
        headers=headers,
        json={"task": "Проверить аварийную остановку перед запуском оборудования"},
    ).json()
    saved = client.post("/api/instructions/history", headers=headers, json={"payload": generated}).json()["record"]
    endpoint = f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/workflow"

    review = client.patch(
        endpoint,
        headers=headers,
        json={
            "status": "expert_review",
            "reviewer": "Поддельный мастер",
            "reviewer_role": "master",
            "comment": "Инструкция передана на экспертную проверку.",
        },
    )
    approved = client.patch(
        endpoint,
        headers=headers,
        json={
            "status": "approved",
            "reviewer": "Поддельный мастер",
            "reviewer_role": "master",
            "comment": "Локальные параметры проверены, инструкция утверждена.",
        },
    )

    assert review.status_code == 200
    assert approved.status_code == 200
    assert approved.json()["record"]["reviewer"] == user["full_name"]
    assert approved.json()["record"]["reviewer_role"] == "safety"
    audit = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}/audit",
        headers=headers,
    ).json()["events"]
    assert audit[0]["actor"] == user["full_name"]
    assert audit[-1]["metadata"]["actor_user_id"] == user["user_id"]
    assert audit[-1]["metadata"]["actor_role"] == "safety"


def test_authenticated_reviewer_validates_specific_claim_with_audit_record(
    tmp_path,
    monkeypatch,
) -> None:
    history_path = tmp_path / "history"
    settings = get_settings().model_copy(
        update={
            "api_access_token": "static-token",
            "database_path": history_path / instruction_history.HISTORY_DATABASE_FILENAME,
        }
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    auth = client.post(
        "/api/auth/register",
        json={
            "email": "claim-validator@example.com",
            "full_name": "Инженер Валидатор",
            "password": "strong-password-1",
            "role": "safety",
        },
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    generated = client.post(
        "/api/instructions/generate",
        headers=headers,
        json={
            "task": "Проверить аварийную остановку перед запуском оборудования",
            "technical_context": "Оператор сообщил, что ограждение установлено перед запуском.",
        },
    ).json()
    saved = client.post(
        "/api/instructions/history",
        headers=headers,
        json={"payload": generated},
    ).json()["record"]
    claim = generated["instruction"]["evidence_claims"][0]
    endpoint = (
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
        f"/claims/{claim['claim_id']}/validate"
    )

    response = client.post(
        endpoint,
        headers=headers,
        json={
            "evidence_reference": "Approved local procedure LP-17 revision 4",
            "evidence_sha256": "a" * 64,
            "comment": "Claim checked against the controlled local procedure.",
        },
    )

    assert response.status_code == 200
    validated = response.json()["claim"]
    assert validated["claim_id"] == claim["claim_id"]
    assert validated["provenance"] == "validated_local"
    assert validated["validation_status"] == "validated"
    assert validated["requires_local_verification"] is False
    assert validated["validation_record"]["reviewer_user_id"] == auth["user"]["user_id"]
    assert validated["validation_record"]["reviewer_name"] == auth["user"]["full_name"]
    assert validated["validation_record"]["reviewer_role"] == "safety"

    detail_url = f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
    detail = client.get(detail_url, headers=headers).json()
    persisted = next(
        item
        for item in detail["payload"]["instruction"]["evidence_claims"]
        if item["claim_id"] == claim["claim_id"]
    )
    assert persisted == validated
    assert "validated_local" in detail["payload"]["markdown"]
    assert "Approved local procedure LP-17 revision 4" in detail["payload"]["markdown"]
    assert detail["payload"]["instruction"]["workflow"]["status"] == "ai_draft"
    audit = client.get(detail_url + "/audit", headers=headers).json()["events"]
    assert [event["event_type"] for event in audit] == ["version_saved", "claim_validated"]
    assert audit[-1]["metadata"]["claim_id"] == claim["claim_id"]
    assert audit[-1]["metadata"]["actor_user_id"] == auth["user"]["user_id"]


def test_client_supplied_validated_claim_is_reset_when_version_is_saved(
    tmp_path,
    monkeypatch,
) -> None:
    history_path = tmp_path / "history"
    settings = get_settings().model_copy(
        update={"database_path": history_path / instruction_history.HISTORY_DATABASE_FILENAME}
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={"task": "Проверить рабочее место перед запуском оборудования"},
    ).json()
    forged = generated["instruction"]["evidence_claims"][0]
    forged["provenance"] = "validated_local"
    forged["validation_status"] = "validated"
    forged["requires_local_verification"] = False
    forged["validation_record"] = {
        "validation_id": "f" * 32,
        "claim_id": forged["claim_id"],
        "evidence_reference": "Client supplied label",
        "evidence_sha256": "b" * 64,
        "reviewer_user_id": "forged-reviewer",
        "reviewer_name": "Forged Reviewer",
        "reviewer_role": "admin",
        "comment": "This record was supplied by the client and is not trusted.",
        "validated_at": "2026-07-15T00:00:00Z",
    }

    saved = client.post("/api/instructions/history", json={"payload": generated}).json()["record"]
    detail = client.get(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
    ).json()
    persisted = detail["payload"]["instruction"]["evidence_claims"][0]

    assert persisted["provenance"] != "validated_local"
    assert persisted["validation_status"] == "unverified"
    assert persisted["requires_local_verification"] is True
    assert persisted["validation_record"] is None


def test_operator_cannot_validate_evidence_claim(tmp_path, monkeypatch) -> None:
    history_path = tmp_path / "history"
    settings = get_settings().model_copy(
        update={"database_path": history_path / instruction_history.HISTORY_DATABASE_FILENAME}
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    auth = client.post(
        "/api/auth/register",
        json={
            "email": "claim-operator@example.com",
            "full_name": "Оператор Claims",
            "password": "strong-password-1",
            "role": "operator",
        },
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    generated = client.post(
        "/api/instructions/generate",
        headers=headers,
        json={"task": "Проверить рабочее место перед запуском оборудования"},
    ).json()
    saved = client.post(
        "/api/instructions/history",
        headers=headers,
        json={"payload": generated},
    ).json()["record"]
    claim_id = generated["instruction"]["evidence_claims"][0]["claim_id"]

    response = client.post(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
        f"/claims/{claim_id}/validate",
        headers=headers,
        json={
            "evidence_reference": "Unapproved operator note",
            "evidence_sha256": "c" * 64,
            "comment": "Operator must not be able to validate this claim.",
        },
    )

    assert response.status_code == 403
    assert "workflow:approve" in response.json()["error"]["message"]


def test_unauthenticated_demo_cannot_validate_evidence_claim(tmp_path, monkeypatch) -> None:
    history_path = tmp_path / "history"
    settings = get_settings().model_copy(
        update={"database_path": history_path / instruction_history.HISTORY_DATABASE_FILENAME}
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        json={"task": "Проверить рабочее место перед запуском оборудования"},
    ).json()
    saved = client.post("/api/instructions/history", json={"payload": generated}).json()["record"]
    claim_id = generated["instruction"]["evidence_claims"][0]["claim_id"]

    response = client.post(
        f"/api/instructions/history/{saved['instruction_id']}/versions/{saved['version']}"
        f"/claims/{claim_id}/validate",
        json={
            "evidence_reference": "Unauthenticated evidence",
            "evidence_sha256": "e" * 64,
            "comment": "Unauthenticated validation must not be accepted.",
        },
    )

    assert response.status_code == 401
    assert "Authenticated reviewer session" in response.json()["error"]["message"]


def test_production_history_is_isolated_between_organizations(tmp_path, monkeypatch) -> None:
    history_path = tmp_path / "history"
    database_path = history_path / instruction_history.HISTORY_DATABASE_FILENAME
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "organization-isolation-bootstrap-token-32-plus",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": database_path,
        }
    )
    monkeypatch.setattr(instruction_history, "INSTRUCTION_HISTORY_DIR", history_path)
    monkeypatch.setattr("app.api.history.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    organization_a = create_organization("Organization A", database_path=database_path)
    organization_b = create_organization("Organization B", database_path=database_path)
    user_a = create_user(
        "safety-a@example.com",
        "Safety A",
        "strong-production-password-a",
        role="safety",
        organization_id=organization_a,
        database_path=database_path,
    )
    user_b = create_user(
        "safety-b@example.com",
        "Safety B",
        "strong-production-password-b",
        role="safety",
        organization_id=organization_b,
        database_path=database_path,
    )
    headers_a = {"Authorization": f"Bearer {create_session(user_a.user_id, database_path=database_path)}"}
    headers_b = {"Authorization": f"Bearer {create_session(user_b.user_id, database_path=database_path)}"}
    client = TestClient(app)
    generated = client.post(
        "/api/instructions/generate",
        headers=headers_a,
        json={"task": "Проверить ограждение перед запуском оборудования"},
    ).json()
    saved_a = client.post(
        "/api/instructions/history",
        headers=headers_a,
        json={"payload": generated},
    ).json()["record"]
    saved_b = client.post(
        "/api/instructions/history",
        headers=headers_b,
        json={"payload": generated},
    ).json()["record"]
    resource_a = f"/api/instructions/history/{saved_a['instruction_id']}/versions/{saved_a['version']}"

    assert saved_a["organization_id"] == organization_a
    assert saved_b["organization_id"] == organization_b
    assert saved_a["instruction_id"] != saved_b["instruction_id"]
    assert len(client.get("/api/instructions/history", headers=headers_a).json()["records"]) == 1
    assert len(client.get("/api/instructions/history", headers=headers_b).json()["records"]) == 1
    assert client.get(resource_a, headers=headers_a).status_code == 200
    assert client.get(resource_a, headers=headers_b).status_code == 404
    assert client.get(resource_a + "/audit", headers=headers_b).status_code == 404
    cross_workflow = client.patch(
        resource_a + "/workflow",
        headers=headers_b,
        json={
            "status": "expert_review",
            "reviewer": "Cross tenant reviewer",
            "reviewer_role": "safety",
            "comment": "This cross-organization update must be rejected.",
        },
    )
    assert cross_workflow.status_code == 404
    claim_id = generated["instruction"]["evidence_claims"][0]["claim_id"]
    cross_validation = client.post(
        resource_a + f"/claims/{claim_id}/validate",
        headers=headers_b,
        json={
            "evidence_reference": "Cross-tenant evidence",
            "evidence_sha256": "d" * 64,
            "comment": "Cross-organization validation must be rejected.",
        },
    )
    assert cross_validation.status_code == 404

    steps = [
        {"label": f"{step['number']}. {step['action']}", "completed": True}
        for step in generated["instruction"]["steps"]
    ]
    execution = client.post(
        resource_a + "/execution",
        headers=headers_a,
        json={"executor": "ignored", "steps": steps, "quality_items": [], "notes": "Org A run"},
    )
    assert execution.status_code == 200
    assert client.get(resource_a + "/execution", headers=headers_b).status_code == 404
    assert client.get("/api/instructions/history/execution-summary", headers=headers_a).json()["total_runs"] == 1
    assert client.get("/api/instructions/history/execution-summary", headers=headers_b).json()["total_runs"] == 0


def _minimal_history_payload(title: str) -> dict:
    return {
        "instruction": {
            "title": title,
            "purpose": "Purpose",
            "scope": "Scope",
            "operator_level": "Новый оператор",
            "required_ppe": ["PPE"],
            "required_tools": ["Tool"],
            "safety_requirements": ["Safety"],
            "hazard_zones": ["Zone"],
            "prerequisites": ["Pre"],
            "steps": [{"number": 1, "action": "Do action", "expected_result": "Done"}],
            "control_points": ["Control"],
            "quality_checklist": ["Quality"],
            "emergency_actions": ["Stop"],
            "common_mistakes": ["Mistake"],
        },
        "markdown": "# Test\n",
        "generation_mode": "fallback",
        "evaluation": {
            "overall_score": 90,
            "criteria": [{"criterion": "completeness", "label": "Полнота", "score": 100}],
            "verdict": "OK",
        },
    }


def _rewrite_stored_mode(database_path, instruction_id: str, legacy_value: str) -> None:
    import json
    import sqlite3

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT record_json, payload_json FROM instruction_versions WHERE instruction_id = ?",
            (instruction_id,),
        ).fetchone()
        record_json = json.loads(row["record_json"])
        payload_json = json.loads(row["payload_json"])
        record_json["generation_mode"] = legacy_value
        payload_json["generation_mode"] = legacy_value
        connection.execute(
            "UPDATE instruction_versions SET record_json = ?, payload_json = ? WHERE instruction_id = ?",
            (
                json.dumps(record_json, ensure_ascii=False),
                json.dumps(payload_json, ensure_ascii=False),
                instruction_id,
            ),
        )
        connection.commit()


@pytest.mark.parametrize(
    ("legacy_value", "expected"),
    [("fallback", "deterministic"), ("openai", "model")],
)
def test_instruction_saved_before_the_rename_still_loads(tmp_path, legacy_value, expected) -> None:
    """A row written with the vendor vocabulary must survive the rename.

    `generation_mode` lives inside the payload JSON, not in a column, and it is
    validated on read. Narrowing the literal without accepting the old spellings
    would not corrupt anything — it would make every stored instruction
    unreadable, which is worse because it looks like data loss.
    """
    payload = generate_instruction(InstructionRequest(task="Проверить оборудование перед запуском смены"))
    record = save_instruction_history(payload, history_dir=tmp_path)
    _rewrite_stored_mode(tmp_path / HISTORY_DATABASE_FILENAME, record.instruction_id, legacy_value)

    detail = get_instruction_history_detail(record.instruction_id, record.version, history_dir=tmp_path)

    assert detail is not None
    assert detail.record.generation_mode == expected
    assert detail.payload.generation_mode == expected
