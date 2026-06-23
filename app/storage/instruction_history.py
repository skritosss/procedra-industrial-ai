from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.core.organization import LEGACY_ORGANIZATION_ID
from app.core.authorization import default_project_id, register_resource_ownership
from app.core.settings import get_settings
from app.schemas.history import (
    AuditEventType,
    InstructionAuditEvent,
    InstructionAuditTrail,
    InstructionExecutionDetail,
    InstructionExecutionItem,
    InstructionExecutionRecord,
    InstructionExecutionSummary,
    InstructionHistoryDetail,
    InstructionHistoryRecord,
    ReviewerRole,
)
from app.schemas.instruction import InstructionLifecycleStatus, InstructionResponse
from app.storage.database import apply_migrations, audit_event_hash, connect_database


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSTRUCTION_HISTORY_DIR = PROJECT_ROOT / "generated" / "instructions"
INSTRUCTION_HISTORY_DIR = DEFAULT_INSTRUCTION_HISTORY_DIR
HISTORY_DATABASE_FILENAME = "instruction_history.sqlite3"


def initialize_instruction_storage() -> None:
    with closing(_open_storage(None)):
        pass


def save_instruction_history(
    payload: InstructionResponse,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
    owner_user_id: str | None = None,
    actor: str = "system",
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    history_dir: Path | None = None,
) -> InstructionHistoryRecord:
    project_id = project_id or default_project_id(organization_id)
    with closing(_open_storage(history_dir)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            instruction_id = _instruction_id(payload, organization_id, project_id)
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM instruction_versions
                WHERE organization_id = ? AND instruction_id = ?
                """,
                (organization_id, instruction_id),
            ).fetchone()
            version = int(row[0])
            created_at = datetime.now(UTC)
            record = _record_from_payload(
                payload,
                instruction_id,
                organization_id,
                version,
                created_at,
                project_id=project_id,
                owner_user_id=owner_user_id,
            )
            connection.execute(
                """
                INSERT INTO instruction_versions (
                    organization_id, instruction_id, version, record_json, payload_json,
                    created_at, updated_at, project_id, owner_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    organization_id,
                    instruction_id,
                    version,
                    _model_json(record),
                    _model_json(payload),
                    created_at.isoformat(),
                    created_at.isoformat(),
                    project_id,
                    owner_user_id,
                ),
            )
            register_resource_ownership(
                organization_id,
                project_id,
                "instruction",
                instruction_id,
                owner_user_id,
                connection=connection,
            )
            audit_event = _audit_event(
                event_type="version_saved",
                actor=actor,
                to_status=record.workflow_status,
                comment="Instruction version saved",
                metadata={
                    "source_count": record.source_count,
                    "step_count": record.step_count,
                    "overall_score": record.overall_score,
                    **_actor_metadata(actor_user_id, actor_role),
                },
            )
            _append_audit_event(connection, organization_id, instruction_id, version, audit_event)
            connection.commit()
            return record
        except Exception:
            connection.rollback()
            raise


def list_instruction_history(
    history_dir: Path | None = None,
    limit: int = 50,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
) -> list[InstructionHistoryRecord]:
    project_id = project_id or default_project_id(organization_id)
    with closing(_open_storage(history_dir)) as connection:
        rows = connection.execute(
            """
            SELECT organization_id, project_id, owner_user_id, instruction_id, version, record_json
            FROM instruction_versions
            WHERE organization_id = ? AND project_id = ?
            ORDER BY created_at DESC, version DESC
            LIMIT ?
            """,
            (organization_id, project_id, limit),
        ).fetchall()
    return [_history_record_from_row(row) for row in rows]


def get_instruction_history_detail(
    instruction_id: str,
    version: int,
    history_dir: Path | None = None,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
) -> InstructionHistoryDetail | None:
    if not _is_safe_instruction_id(instruction_id) or version < 1:
        return None
    with closing(_open_storage(history_dir)) as connection:
        return _get_detail(
            connection,
            organization_id,
            project_id or default_project_id(organization_id),
            instruction_id,
            version,
        )


def get_instruction_audit_trail(
    instruction_id: str,
    version: int,
    history_dir: Path | None = None,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
) -> InstructionAuditTrail | None:
    detail = get_instruction_history_detail(
        instruction_id,
        version,
        history_dir,
        organization_id,
        project_id,
    )
    if detail is None:
        return None
    return InstructionAuditTrail(events=detail.audit_events)


def update_instruction_workflow_status(
    instruction_id: str,
    version: int,
    status: InstructionLifecycleStatus,
    reviewer: str,
    reviewer_role: ReviewerRole,
    comment: str,
    resolved_blockers: list[str] | None = None,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    history_dir: Path | None = None,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
) -> InstructionHistoryRecord | None:
    if not _is_safe_instruction_id(instruction_id) or version < 1:
        return None
    project_id = project_id or default_project_id(organization_id)
    with closing(_open_storage(history_dir)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            detail = _get_detail(connection, organization_id, project_id, instruction_id, version)
            if detail is None:
                connection.rollback()
                return None

            _validate_workflow_transition(detail.payload.instruction.workflow.status, status)
            _validate_reviewer_role(status, reviewer_role)
            previous_status = detail.payload.instruction.workflow.status
            reviewed_at = datetime.now(UTC)
            resolved = _clean_string_list(resolved_blockers or [])
            status_label = _status_label(status)
            role_label = _reviewer_role_label(reviewer_role)
            workflow = detail.payload.instruction.workflow
            workflow.status = status
            workflow.status_label = status_label
            workflow.next_actions = _next_actions_for_status(status, reviewer, reviewer_role, comment)
            if status == "approved":
                workflow.approval_blockers = [
                    f"Блокеры утверждения закрыты решением ответственного лица: {reviewer.strip()} ({role_label})."
                ]
            elif resolved:
                workflow.approval_blockers = [
                    blocker for blocker in workflow.approval_blockers if blocker not in resolved
                ]

            detail.record.workflow_status = status
            detail.record.workflow_status_label = status_label
            detail.record.reviewer = reviewer.strip()
            detail.record.reviewer_role = reviewer_role
            detail.record.review_comment = comment.strip()
            detail.record.reviewed_at = reviewed_at
            detail.record.resolved_blockers = resolved
            connection.execute(
                """
                UPDATE instruction_versions
                SET record_json = ?, payload_json = ?, updated_at = ?
                WHERE organization_id = ? AND project_id = ? AND instruction_id = ? AND version = ?
                """,
                (
                    _model_json(detail.record),
                    _model_json(detail.payload),
                    reviewed_at.isoformat(),
                    organization_id,
                    project_id,
                    instruction_id,
                    version,
                ),
            )
            _append_audit_event(
                connection,
                organization_id,
                instruction_id,
                version,
                _audit_event(
                    event_type="workflow_updated",
                    actor=reviewer.strip(),
                    reviewer_role=reviewer_role,
                    from_status=previous_status,
                    to_status=status,
                    comment=comment.strip(),
                    metadata={
                        "resolved_blockers": len(resolved),
                        **_actor_metadata(actor_user_id, actor_role),
                    },
                ),
            )
            connection.commit()
            return detail.record
        except Exception:
            connection.rollback()
            raise


def save_instruction_execution(
    instruction_id: str,
    version: int,
    executor: str,
    notes: str,
    steps: list[InstructionExecutionItem],
    quality_items: list[InstructionExecutionItem] | None = None,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    history_dir: Path | None = None,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
    owner_user_id: str | None = None,
) -> InstructionExecutionRecord | None:
    if not _is_safe_instruction_id(instruction_id) or version < 1:
        return None
    project_id = project_id or default_project_id(organization_id)
    with closing(_open_storage(history_dir)) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            detail = _get_detail(connection, organization_id, project_id, instruction_id, version)
            if detail is None:
                connection.rollback()
                return None
            quality_items = quality_items or []
            _validate_execution_items(detail, steps, quality_items)
            created_at = datetime.now(UTC)
            run_id = f"{created_at.strftime('%Y%m%d%H%M%S%f')}-{os.urandom(4).hex()}"
            record = InstructionExecutionRecord(
                run_id=run_id,
                instruction_id=instruction_id,
                organization_id=organization_id,
                project_id=project_id,
                owner_user_id=owner_user_id,
                version=version,
                created_at=created_at,
                executor=executor.strip(),
                notes=notes.strip(),
                completed_steps=sum(1 for item in steps if item.completed),
                total_steps=len(steps),
                completed_quality_items=sum(1 for item in quality_items if item.completed),
                total_quality_items=len(quality_items),
            )
            execution_detail = InstructionExecutionDetail(
                record=record,
                steps=steps,
                quality_items=quality_items,
            )
            connection.execute(
                """
                INSERT INTO instruction_execution_runs (
                    run_id, organization_id, instruction_id, version,
                    record_json, detail_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    organization_id,
                    instruction_id,
                    version,
                    _model_json(record),
                    _model_json(execution_detail),
                    created_at.isoformat(),
                ),
            )
            _append_audit_event(
                connection,
                organization_id,
                instruction_id,
                version,
                _audit_event(
                    event_type="execution_saved",
                    actor=executor.strip(),
                    to_status=detail.payload.instruction.workflow.status,
                    comment=notes.strip() or "Execution run saved",
                    metadata={
                        "run_id": run_id,
                        "completed_steps": record.completed_steps,
                        "total_steps": record.total_steps,
                        "completed_quality_items": record.completed_quality_items,
                        "total_quality_items": record.total_quality_items,
                        **_actor_metadata(actor_user_id, actor_role),
                    },
                ),
            )
            connection.commit()
            return record
        except Exception:
            connection.rollback()
            raise


def list_instruction_executions(
    instruction_id: str,
    version: int,
    history_dir: Path | None = None,
    limit: int = 50,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
) -> list[InstructionExecutionRecord] | None:
    if not _is_safe_instruction_id(instruction_id) or version < 1:
        return None
    project_id = project_id or default_project_id(organization_id)
    with closing(_open_storage(history_dir)) as connection:
        parent = _get_version_row(connection, organization_id, project_id, instruction_id, version)
        if parent is None:
            return None
        rows = connection.execute(
            """
            SELECT record_json
            FROM instruction_execution_runs
            WHERE organization_id = ? AND instruction_id = ? AND version = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (organization_id, instruction_id, version, limit),
        ).fetchall()
    return [
        _execution_record_for_scope(
            InstructionExecutionRecord.model_validate_json(str(row["record_json"])),
            organization_id,
            project_id,
            instruction_id,
            version,
        )
        for row in rows
    ]


def summarize_instruction_executions(
    history_dir: Path | None = None,
    latest_limit: int = 5,
    organization_id: str = LEGACY_ORGANIZATION_ID,
    project_id: str | None = None,
) -> InstructionExecutionSummary:
    project_id = project_id or default_project_id(organization_id)
    with closing(_open_storage(history_dir)) as connection:
        rows = connection.execute(
            """
            SELECT e.record_json
            FROM instruction_execution_runs e
            JOIN instruction_versions i
              ON i.organization_id = e.organization_id
             AND i.instruction_id = e.instruction_id
             AND i.version = e.version
            WHERE e.organization_id = ? AND i.project_id = ?
            ORDER BY e.created_at DESC
            """,
            (organization_id, project_id),
        ).fetchall()
    records = [
        _execution_record_for_scope(
            InstructionExecutionRecord.model_validate_json(str(row["record_json"])),
            organization_id,
            project_id,
        )
        for row in rows
    ]
    total_steps = sum(record.total_steps for record in records)
    completed_steps = sum(record.completed_steps for record in records)
    total_quality_items = sum(record.total_quality_items for record in records)
    completed_quality_items = sum(record.completed_quality_items for record in records)
    return InstructionExecutionSummary(
        total_runs=len(records),
        total_steps=total_steps,
        completed_steps=completed_steps,
        total_quality_items=total_quality_items,
        completed_quality_items=completed_quality_items,
        step_completion_rate=_completion_rate(completed_steps, total_steps),
        quality_completion_rate=_completion_rate(completed_quality_items, total_quality_items),
        latest_runs=records[:latest_limit],
    )


def _open_storage(history_dir: Path | None) -> sqlite3.Connection:
    legacy_dir = history_dir or INSTRUCTION_HISTORY_DIR
    database_path = _history_database_path(history_dir)
    connection = connect_database(database_path)
    apply_migrations(connection)
    _import_legacy_history(connection, legacy_dir)
    return connection


def _history_database_path(history_dir: Path | None) -> Path:
    if history_dir is not None:
        return history_dir / HISTORY_DATABASE_FILENAME
    if INSTRUCTION_HISTORY_DIR != DEFAULT_INSTRUCTION_HISTORY_DIR:
        return INSTRUCTION_HISTORY_DIR / HISTORY_DATABASE_FILENAME
    return get_settings().database_path


def _get_version_row(
    connection: sqlite3.Connection,
    organization_id: str,
    project_id: str,
    instruction_id: str,
    version: int,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT organization_id, project_id, owner_user_id, instruction_id, version,
               record_json, payload_json
        FROM instruction_versions
        WHERE organization_id = ? AND project_id = ? AND instruction_id = ? AND version = ?
        """,
        (organization_id, project_id, instruction_id, version),
    ).fetchone()


def _get_detail(
    connection: sqlite3.Connection,
    organization_id: str,
    project_id: str,
    instruction_id: str,
    version: int,
) -> InstructionHistoryDetail | None:
    row = _get_version_row(connection, organization_id, project_id, instruction_id, version)
    if row is None:
        return None
    audit_rows = connection.execute(
        """
        SELECT event_json
        FROM instruction_audit_events
        WHERE organization_id = ? AND instruction_id = ? AND version = ?
        ORDER BY sequence
        """,
        (organization_id, instruction_id, version),
    ).fetchall()
    return InstructionHistoryDetail(
        record=_history_record_from_row(row),
        payload=InstructionResponse.model_validate_json(str(row["payload_json"])),
        audit_events=[InstructionAuditEvent.model_validate_json(str(item["event_json"])) for item in audit_rows],
    )


def _append_audit_event(
    connection: sqlite3.Connection,
    organization_id: str,
    instruction_id: str,
    version: int,
    event: InstructionAuditEvent,
) -> None:
    previous = connection.execute(
        """
        SELECT sequence, event_hash
        FROM instruction_audit_events
        WHERE organization_id = ? AND instruction_id = ? AND version = ?
        ORDER BY sequence DESC
        LIMIT 1
        """,
        (organization_id, instruction_id, version),
    ).fetchone()
    sequence = int(previous["sequence"]) + 1 if previous else 1
    previous_hash = str(previous["event_hash"]) if previous else ""
    event_json = _model_json(event)
    event_hash = audit_event_hash(
        organization_id,
        instruction_id,
        version,
        sequence,
        previous_hash,
        event_json,
    )
    connection.execute(
        """
        INSERT INTO instruction_audit_events (
            event_id, organization_id, instruction_id, version, sequence,
            event_json, created_at, previous_event_hash, event_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.event_id,
            organization_id,
            instruction_id,
            version,
            sequence,
            event_json,
            event.created_at.isoformat(),
            previous_hash,
            event_hash,
        ),
    )


def _import_legacy_history(connection: sqlite3.Connection, history_dir: Path) -> None:
    if not history_dir.exists():
        return
    record_paths = sorted(path for path in history_dir.glob("*.json") if "-execution-" not in path.name)
    execution_paths = sorted(path for path in history_dir.glob("*-execution-*.json"))
    pending_paths = [
        path
        for path in [*record_paths, *execution_paths]
        if not _legacy_source_imported(connection, path)
    ]
    if not pending_paths:
        return
    pending = {path.resolve() for path in pending_paths}
    record_paths = [path for path in record_paths if path.resolve() in pending]
    execution_paths = [path for path in execution_paths if path.resolve() in pending]
    try:
        connection.execute("BEGIN IMMEDIATE")
        for path in record_paths:
            _import_legacy_record(connection, path)
        for path in execution_paths:
            _import_legacy_execution(connection, path)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def _import_legacy_record(connection: sqlite3.Connection, path: Path) -> None:
    content = path.read_bytes()
    if _legacy_source_imported(connection, path):
        return
    try:
        detail = InstructionHistoryDetail.model_validate_json(content)
    except ValueError:
        return
    record = detail.record
    project_id = _normalized_project_id(record.organization_id, record.project_id)
    if project_id != record.project_id:
        record = record.model_copy(update={"project_id": project_id})
    connection.execute(
        """
        INSERT OR IGNORE INTO instruction_versions (
            organization_id, project_id, owner_user_id, instruction_id, version,
            record_json, payload_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.organization_id,
            project_id,
            record.owner_user_id,
            record.instruction_id,
            record.version,
            _model_json(record),
            _model_json(detail.payload),
            record.created_at.isoformat(),
            (record.reviewed_at or record.created_at).isoformat(),
        ),
    )
    register_resource_ownership(
        record.organization_id,
        project_id,
        "instruction",
        record.instruction_id,
        record.owner_user_id,
        connection=connection,
    )
    for event in detail.audit_events:
        exists = connection.execute(
            "SELECT 1 FROM instruction_audit_events WHERE event_id = ?",
            (event.event_id,),
        ).fetchone()
        if not exists:
            _append_audit_event(
                connection,
                record.organization_id,
                record.instruction_id,
                record.version,
                event,
            )
    _mark_legacy_source(connection, path, content)


def _import_legacy_execution(connection: sqlite3.Connection, path: Path) -> None:
    content = path.read_bytes()
    if _legacy_source_imported(connection, path):
        return
    try:
        detail = InstructionExecutionDetail.model_validate_json(content)
    except ValueError:
        return
    record = detail.record
    project_id = _normalized_project_id(record.organization_id, record.project_id)
    if project_id != record.project_id:
        record = record.model_copy(update={"project_id": project_id})
        detail = detail.model_copy(update={"record": record})
    parent = _get_version_row(
        connection,
        record.organization_id,
        project_id,
        record.instruction_id,
        record.version,
    )
    if parent is None:
        return
    connection.execute(
        """
        INSERT OR IGNORE INTO instruction_execution_runs (
            run_id, organization_id, instruction_id, version, record_json, detail_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.run_id,
            record.organization_id,
            record.instruction_id,
            record.version,
            _model_json(record),
            _model_json(detail),
            record.created_at.isoformat(),
        ),
    )
    _mark_legacy_source(connection, path, content)


def _legacy_source_imported(connection: sqlite3.Connection, path: Path) -> bool:
    return bool(
        connection.execute(
            "SELECT 1 FROM legacy_history_imports WHERE source_path = ?",
            (str(path.resolve()),),
        ).fetchone()
    )


def _mark_legacy_source(connection: sqlite3.Connection, path: Path, content: bytes) -> None:
    connection.execute(
        """
        INSERT INTO legacy_history_imports (source_path, source_sha256, imported_at)
        VALUES (?, ?, ?)
        """,
        (str(path.resolve()), hashlib.sha256(content).hexdigest(), datetime.now(UTC).isoformat()),
    )


def _model_json(model) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _history_record_from_row(row: sqlite3.Row) -> InstructionHistoryRecord:
    record = InstructionHistoryRecord.model_validate_json(str(row["record_json"]))
    organization_id = str(row["organization_id"])
    project_id = str(row["project_id"])
    instruction_id = str(row["instruction_id"])
    version = int(row["version"])
    if record.project_id == LEGACY_ORGANIZATION_ID and project_id == default_project_id(organization_id):
        record = record.model_copy(update={"project_id": project_id})
    if (
        record.organization_id != organization_id
        or record.project_id != project_id
        or record.instruction_id != instruction_id
        or record.version != version
    ):
        raise ValueError("Instruction record scope does not match its database row")
    owner_user_id = str(row["owner_user_id"]) if row["owner_user_id"] else None
    if record.owner_user_id is None and owner_user_id is not None:
        record = record.model_copy(update={"owner_user_id": owner_user_id})
    elif record.owner_user_id != owner_user_id:
        raise ValueError("Instruction record owner does not match its database row")
    return record


def _execution_record_for_scope(
    record: InstructionExecutionRecord,
    organization_id: str,
    project_id: str,
    instruction_id: str | None = None,
    version: int | None = None,
) -> InstructionExecutionRecord:
    if record.project_id == LEGACY_ORGANIZATION_ID and project_id == default_project_id(organization_id):
        record = record.model_copy(update={"project_id": project_id})
    if record.organization_id != organization_id or record.project_id != project_id:
        raise ValueError("Execution record scope does not match its instruction project")
    if instruction_id is not None and record.instruction_id != instruction_id:
        raise ValueError("Execution record instruction does not match its database row")
    if version is not None and record.version != version:
        raise ValueError("Execution record version does not match its database row")
    return record


def _completion_rate(completed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100 * completed / total, 1)


def _validate_execution_items(
    detail: InstructionHistoryDetail,
    steps: list[InstructionExecutionItem],
    quality_items: list[InstructionExecutionItem],
) -> None:
    expected_steps = _execution_step_labels(detail)
    submitted_steps = [item.label.strip() for item in steps]
    if submitted_steps != expected_steps:
        raise ValueError("Execution steps must match the saved instruction version")

    allowed_quality_items = set(_execution_quality_labels(detail))
    unknown_quality_items = sorted(
        {item.label.strip() for item in quality_items if item.label.strip() not in allowed_quality_items}
    )
    if unknown_quality_items:
        raise ValueError("Execution quality items must match the saved instruction version")


def _execution_step_labels(detail: InstructionHistoryDetail) -> list[str]:
    return [f"{step.number}. {step.action}".strip() for step in detail.payload.instruction.steps]


def _execution_quality_labels(detail: InstructionHistoryDetail) -> list[str]:
    control_points = [item.strip() for item in detail.payload.instruction.control_points if item.strip()]
    return [
        "Все обязательные контрольные точки выполнены и подтверждены ответственным лицом.",
        "Рабочее место и оборудование находятся в безопасном, определенном состоянии.",
        "Отклонения, замечания и ограничения зафиксированы в принятой на участке форме.",
        "All mandatory control points are completed and confirmed by the responsible person.",
        "The workplace and equipment are in a safe, defined state.",
        "Deviations, remarks, and limits are recorded in the accepted local form.",
        *control_points,
    ]


def _is_safe_instruction_id(value: str) -> bool:
    if not value or len(value) > 120:
        return False
    if any(char in value for char in ("/", "\\", ".", "\x00")):
        return False
    return all(char.isalnum() or char in {"-", "_"} for char in value)


def _instruction_id(payload: InstructionResponse, organization_id: str, project_id: str) -> str:
    instruction = payload.instruction
    digest_input = {
        "title": instruction.title,
        "purpose": instruction.purpose,
        "scope": instruction.scope,
        "steps": [step.model_dump(mode="json") for step in instruction.steps],
        "organization_id": organization_id,
        "project_id": project_id,
    }
    digest = hashlib.sha256(
        json.dumps(digest_input, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:14]
    slug = _slug(instruction.title)
    return f"{slug}-{digest}"[:96].strip("-") or digest


def _record_from_payload(
    payload: InstructionResponse,
    instruction_id: str,
    organization_id: str,
    version: int,
    created_at: datetime,
    project_id: str | None = None,
    owner_user_id: str | None = None,
) -> InstructionHistoryRecord:
    project_id = project_id or default_project_id(organization_id)
    workflow = payload.instruction.workflow
    return InstructionHistoryRecord(
        instruction_id=instruction_id,
        organization_id=organization_id,
        project_id=project_id,
        owner_user_id=owner_user_id,
        version=version,
        title=payload.instruction.title,
        created_at=created_at,
        generation_mode=payload.generation_mode,
        overall_score=payload.evaluation.overall_score,
        risk_level=payload.evaluation.risk_level,
        workflow_status=workflow.status,
        workflow_status_label=workflow.status_label,
        source_count=len(payload.sources),
        step_count=len(payload.instruction.steps),
    )


def _normalized_project_id(organization_id: str, project_id: str) -> str:
    if project_id == LEGACY_ORGANIZATION_ID and organization_id != LEGACY_ORGANIZATION_ID:
        return default_project_id(organization_id)
    return project_id


def _status_label(status: InstructionLifecycleStatus) -> str:
    labels = {
        "ai_draft": "AI-черновик",
        "expert_review": "На экспертной проверке",
        "approved": "Утверждено",
        "rejected": "Отклонено",
    }
    return labels[status]


def _audit_event(
    event_type: AuditEventType,
    actor: str,
    to_status: InstructionLifecycleStatus | None = None,
    reviewer_role: ReviewerRole | None = None,
    from_status: InstructionLifecycleStatus | None = None,
    comment: str | None = None,
    metadata: dict[str, str | int | float | bool] | None = None,
) -> InstructionAuditEvent:
    return InstructionAuditEvent(
        event_id=os.urandom(16).hex(),
        created_at=datetime.now(UTC),
        event_type=event_type,
        actor=actor.strip() or "system",
        reviewer_role=reviewer_role,
        from_status=from_status,
        to_status=to_status,
        comment=comment.strip() if comment else None,
        metadata=metadata or {},
    )


def _actor_metadata(actor_user_id: str | None, actor_role: str | None) -> dict[str, str]:
    metadata = {}
    if actor_user_id:
        metadata["actor_user_id"] = actor_user_id
    if actor_role:
        metadata["actor_role"] = actor_role
    return metadata


def _validate_workflow_transition(
    current_status: InstructionLifecycleStatus,
    next_status: InstructionLifecycleStatus,
) -> None:
    if current_status == next_status:
        return
    allowed = {
        "ai_draft": {"expert_review", "rejected"},
        "expert_review": {"approved", "rejected", "ai_draft"},
        "approved": {"expert_review"},
        "rejected": {"ai_draft", "expert_review"},
    }
    if next_status not in allowed[current_status]:
        raise ValueError(f"Invalid workflow transition: {current_status} -> {next_status}")


def _validate_reviewer_role(status: InstructionLifecycleStatus, reviewer_role: ReviewerRole) -> None:
    if status == "approved" and reviewer_role not in {"technologist", "safety", "quality", "admin"}:
        raise ValueError("Only technologist, safety, quality, or admin roles can approve instruction versions")


def _reviewer_role_label(reviewer_role: ReviewerRole) -> str:
    labels = {
        "master": "Мастер смены/руководитель участка",
        "technologist": "Инженер/технолог",
        "safety": "Специалист по охране труда/ПБ",
        "quality": "Специалист по качеству",
        "admin": "Администратор системы",
    }
    return labels[reviewer_role]


def _next_actions_for_status(
    status: InstructionLifecycleStatus,
    reviewer: str,
    reviewer_role: ReviewerRole,
    comment: str,
) -> list[str]:
    reviewer = reviewer.strip()
    role_label = _reviewer_role_label(reviewer_role)
    comment = comment.strip()
    if status == "expert_review":
        return [
            f"Версия передана на экспертную проверку: {reviewer} ({role_label}).",
            f"Комментарий проверки: {comment}",
            "После проверки зафиксировать решение: утверждение, отклонение или возврат на доработку.",
        ]
    if status == "approved":
        return [
            f"Версия утверждена: {reviewer} ({role_label}).",
            f"Комментарий решения: {comment}",
            "Перед выдачей оператору сверить актуальность локальной документации и условий рабочего места.",
        ]
    if status == "rejected":
        return [
            f"Версия отклонена: {reviewer} ({role_label}).",
            f"Причина отклонения: {comment}",
            "Исправить замечания и сохранить новую версию либо вернуть текущую версию в AI-черновик.",
        ]
    return [
        f"Версия возвращена в AI-черновик: {reviewer} ({role_label}).",
        f"Комментарий возврата: {comment}",
        "Доработать инструкцию и повторно передать ее на экспертную проверку.",
    ]


def _clean_string_list(items: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for item in items:
        value = " ".join(item.split())
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        cleaned.append(value)
    return cleaned


def _slug(value: str) -> str:
    normalized = value.lower().replace("ё", "е")
    slug = "-".join(part for part in _split_slug_parts(normalized) if part)
    return slug[:72].strip("-") or "instruction"


def _split_slug_parts(value: str) -> list[str]:
    result = []
    current = []
    for char in value:
        if char.isalnum():
            current.append(char)
        elif current:
            result.append("".join(current))
            current = []
    if current:
        result.append("".join(current))
    return result
