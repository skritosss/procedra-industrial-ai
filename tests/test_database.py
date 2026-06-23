import json
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.evaluation.quality import evaluate_instruction
from app.generation.fallback import generate_fallback_instruction
from app.generation.markdown import render_instruction_markdown
from app.schemas.instruction import InstructionRequest, InstructionResponse
from app.storage import instruction_history
from app.storage import database as database_module
from app.storage.database import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    apply_migrations,
    backup_database,
    connect_database,
    database_is_healthy,
    restore_database,
    verify_database,
)
from scripts import manage_database


def _payload() -> InstructionResponse:
    request = InstructionRequest(task="Проверить защитное ограждение перед запуском оборудования")
    instruction = generate_fallback_instruction(request)
    return InstructionResponse(
        instruction=instruction,
        markdown=render_instruction_markdown(instruction),
        generation_mode="fallback",
        evaluation=evaluate_instruction(instruction, request),
    )


def _save_payload_process(history_dir: str, payload_json: str) -> int:
    payload = InstructionResponse.model_validate_json(payload_json)
    return instruction_history.save_instruction_history(payload, history_dir=Path(history_dir)).version


def _seed_valid_schema_v6(connection: sqlite3.Connection) -> dict[str, str]:
    connection.execute(
        """
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    for version, name, migration in MIGRATIONS:
        if version > 6:
            break
        connection.execute("BEGIN IMMEDIATE")
        migration(connection, 86_400)
        connection.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, datetime.now(UTC).isoformat()),
        )
        connection.commit()
    now = datetime.now(UTC).isoformat()
    organization_a = "legacy-a"
    organization_b = "legacy-b"
    user_a = "legacy-user-a"
    user_b = "legacy-user-b"
    project_b = "legacy-project-b"
    connection.executemany(
        "INSERT INTO organizations (organization_id, name, created_at) VALUES (?, ?, ?)",
        [
            (organization_a, "Legacy A", now),
            (organization_b, "Legacy B", now),
        ],
    )
    connection.executemany(
        """
        INSERT INTO projects (project_id, organization_id, name, is_default, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (organization_a, organization_a, "Legacy A Default", 1, now),
            (organization_b, organization_b, "Legacy B Default", 1, now),
            (project_b, organization_b, "Legacy B Project", 0, now),
        ],
    )
    connection.executemany(
        """
        INSERT INTO users (
            user_id, organization_id, email, full_name, role,
            password_hash, is_active, created_at
        ) VALUES (?, ?, ?, ?, 'operator', 'invalid-test-hash', 1, ?)
        """,
        [
            (user_a, organization_a, "legacy-a@example.com", "Legacy User A", now),
            (user_b, organization_b, "legacy-b@example.com", "Legacy User B", now),
        ],
    )
    connection.executemany(
        """
        INSERT INTO project_members (organization_id, project_id, user_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        [
            (organization_a, organization_a, user_a, now),
            (organization_b, organization_b, user_b, now),
            (organization_b, project_b, user_b, now),
        ],
    )
    connection.commit()
    return {
        "organization_a": organization_a,
        "organization_b": organization_b,
        "user_a": user_a,
        "user_b": user_b,
        "project_b": project_b,
    }


def test_versioned_migrations_create_transactional_lifecycle_schema(tmp_path) -> None:
    database_path = tmp_path / "app.sqlite3"

    with connect_database(database_path) as connection:
        first = apply_migrations(connection)
        second = apply_migrations(connection)
        versions = connection.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }

    assert first == second == CURRENT_SCHEMA_VERSION
    assert [(row[0], row[1]) for row in versions] == [
        (1, "auth_foundation"),
        (2, "instruction_lifecycle"),
        (3, "project_ownership"),
        (4, "admin_lifecycle"),
        (5, "shared_rate_limit"),
        (6, "browser_session_csrf"),
        (7, "composite_tenant_foreign_keys"),
    ]
    assert {
        "instruction_versions",
        "instruction_audit_events",
        "instruction_execution_runs",
        "projects",
        "project_members",
        "resource_ownership",
        "admin_invitations",
        "admin_audit_events",
        "rate_limit_events",
    } <= tables


def test_composite_tenant_migration_preserves_valid_v6_rows(tmp_path) -> None:
    database_path = tmp_path / "valid-v6.sqlite3"
    with connect_database(database_path) as connection:
        identifiers = _seed_valid_schema_v6(connection)
        membership_count = connection.execute("SELECT COUNT(*) FROM project_members").fetchone()[0]
        assert apply_migrations(connection) == CURRENT_SCHEMA_VERSION
        assert connection.execute("SELECT COUNT(*) FROM project_members").fetchone()[0] == membership_count
        connection.execute(
            """
            INSERT INTO resource_ownership (
                organization_id, project_id, resource_type, resource_id, owner_user_id, created_at
            ) VALUES (?, ?, 'document', 'valid-resource', ?, ?)
            """,
            (
                identifiers["organization_b"],
                identifiers["project_b"],
                identifiers["user_b"],
                datetime.now(UTC).isoformat(),
            ),
        )

    assert verify_database(database_path)["schema_version"] == CURRENT_SCHEMA_VERSION


def test_composite_tenant_migration_rejects_corrupt_v6_rows_before_rebuild(tmp_path) -> None:
    database_path = tmp_path / "corrupt-v6.sqlite3"
    with connect_database(database_path) as connection:
        identifiers = _seed_valid_schema_v6(connection)
        connection.execute(
            """
            INSERT INTO project_members (organization_id, project_id, user_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                identifiers["organization_a"],
                identifiers["project_b"],
                identifiers["user_a"],
                datetime.now(UTC).isoformat(),
            ),
        )
        connection.commit()

        with pytest.raises(ValueError, match="pre-migration validation"):
            apply_migrations(connection)

        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM project_members").fetchone()[0] == 4
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'project_members_v7'"
        ).fetchone() is None


def test_composite_tenant_migration_rolls_back_rebuilt_tables_on_failure(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "rollback-v6.sqlite3"
    original_migration = MIGRATIONS[-1][2]

    def fail_after_rebuild(connection: sqlite3.Connection, ttl_seconds: int) -> None:
        original_migration(connection, ttl_seconds)
        raise RuntimeError("injected post-rebuild failure")

    monkeypatch.setattr(
        database_module,
        "MIGRATIONS",
        (*MIGRATIONS[:-1], (7, "composite_tenant_foreign_keys", fail_after_rebuild)),
    )
    with connect_database(database_path) as connection:
        _seed_valid_schema_v6(connection)
        with pytest.raises(RuntimeError, match="post-rebuild failure"):
            apply_migrations(connection)

        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM project_members").fetchone()[0] == 3
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'project_members_v7'"
        ).fetchone() is None
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_users_organization_user'"
        ).fetchone() is None


def test_migrations_reject_newer_unsupported_schema(tmp_path) -> None:
    database_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (99, 'future', ?)",
            (datetime.now(UTC).isoformat(),),
        )

    with connect_database(database_path) as connection:
        with pytest.raises(ValueError, match="newer than supported"):
            apply_migrations(connection)


def test_migrations_reject_unexpected_identity(tmp_path) -> None:
    database_path = tmp_path / "renamed.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (1, 'wrong-name', ?)",
            (datetime.now(UTC).isoformat(),),
        )

    with connect_database(database_path) as connection:
        with pytest.raises(ValueError, match="unexpected name"):
            apply_migrations(connection)


def test_concurrent_history_saves_allocate_unique_versions(tmp_path) -> None:
    payload = _payload()

    def save(_: int) -> int:
        return instruction_history.save_instruction_history(payload, history_dir=tmp_path).version

    with ThreadPoolExecutor(max_workers=8) as executor:
        versions = list(executor.map(save, range(20)))

    assert sorted(versions) == list(range(1, 21))
    records = instruction_history.list_instruction_history(history_dir=tmp_path, limit=25)
    assert len(records) == 20


def test_multi_process_history_saves_allocate_unique_versions(tmp_path) -> None:
    payload_json = _payload().model_dump_json()

    try:
        with ProcessPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(_save_payload_process, str(tmp_path), payload_json) for _ in range(8)]
            versions = [future.result(timeout=20) for future in futures]
    except (NotImplementedError, PermissionError) as exc:
        pytest.skip(f"Process pools are unavailable in this sandbox: {exc}")

    assert sorted(versions) == list(range(1, 9))


def test_concurrent_workflow_updates_are_atomic_and_append_audit_events(tmp_path) -> None:
    record = instruction_history.save_instruction_history(_payload(), history_dir=tmp_path)

    def review(index: int) -> str:
        updated = instruction_history.update_instruction_workflow_status(
            record.instruction_id,
            record.version,
            status="expert_review",
            reviewer=f"Reviewer {index}",
            reviewer_role="master",
            comment=f"Concurrent review event number {index}",
            history_dir=tmp_path,
        )
        assert updated is not None
        return updated.workflow_status

    with ThreadPoolExecutor(max_workers=6) as executor:
        statuses = list(executor.map(review, range(10)))

    assert statuses == ["expert_review"] * 10
    detail = instruction_history.get_instruction_history_detail(
        record.instruction_id,
        record.version,
        history_dir=tmp_path,
    )
    assert detail is not None
    assert len(detail.audit_events) == 11
    assert verify_database(tmp_path / instruction_history.HISTORY_DATABASE_FILENAME)["audit_chain"] == "ok"


def test_audit_events_are_append_only_and_hash_chain_verifies(tmp_path) -> None:
    record = instruction_history.save_instruction_history(_payload(), history_dir=tmp_path)
    database_path = tmp_path / instruction_history.HISTORY_DATABASE_FILENAME

    result = verify_database(database_path)
    assert result["audit_events"] == 1
    assert result["audit_chain"] == "ok"

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE instruction_audit_events SET event_json = '{}' WHERE instruction_id = ?",
                (record.instruction_id,),
            )


def test_audit_hash_chain_detects_out_of_band_tampering(tmp_path) -> None:
    instruction_history.save_instruction_history(_payload(), history_dir=tmp_path)
    database_path = tmp_path / instruction_history.HISTORY_DATABASE_FILENAME
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TRIGGER instruction_audit_events_no_update")
        connection.execute("UPDATE instruction_audit_events SET event_json = '{}' ")

    with pytest.raises(ValueError, match="hash is invalid"):
        verify_database(database_path)
    assert database_is_healthy(database_path) is False


def test_execution_and_audit_write_roll_back_together(tmp_path, monkeypatch) -> None:
    record = instruction_history.save_instruction_history(_payload(), history_dir=tmp_path)
    detail = instruction_history.get_instruction_history_detail(
        record.instruction_id,
        record.version,
        history_dir=tmp_path,
    )
    assert detail is not None
    steps = [
        {"label": f"{step.number}. {step.action}", "completed": True}
        for step in detail.payload.instruction.steps
    ]
    from app.schemas.history import InstructionExecutionItem

    execution_steps = [InstructionExecutionItem.model_validate(step) for step in steps]
    monkeypatch.setattr(
        instruction_history,
        "_append_audit_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit insert failed")),
    )

    with pytest.raises(RuntimeError, match="audit insert failed"):
        instruction_history.save_instruction_execution(
            record.instruction_id,
            record.version,
            executor="Test Operator",
            notes="Atomic rollback test",
            steps=execution_steps,
            history_dir=tmp_path,
        )

    with sqlite3.connect(tmp_path / instruction_history.HISTORY_DATABASE_FILENAME) as connection:
        assert connection.execute("SELECT COUNT(*) FROM instruction_execution_runs").fetchone()[0] == 0


def test_legacy_json_is_imported_once_and_preserved(tmp_path) -> None:
    payload = _payload()
    record = instruction_history._record_from_payload(
        payload,
        "legacy-import-test",
        "legacy",
        1,
        datetime.now(UTC),
    )
    source = tmp_path / "legacy-import-test-v1.json"
    source.write_text(
        json.dumps(
            {
                "record": record.model_dump(mode="json"),
                "payload": payload.model_dump(mode="json"),
                "audit_events": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    first = instruction_history.list_instruction_history(history_dir=tmp_path)
    second = instruction_history.list_instruction_history(history_dir=tmp_path)

    assert [item.instruction_id for item in first] == ["legacy-import-test"]
    assert [item.instruction_id for item in second] == ["legacy-import-test"]
    assert source.is_file()
    with sqlite3.connect(tmp_path / instruction_history.HISTORY_DATABASE_FILENAME) as connection:
        assert connection.execute("SELECT COUNT(*) FROM legacy_history_imports").fetchone()[0] == 1


def test_history_read_rejects_record_scope_tampering(tmp_path) -> None:
    record = instruction_history.save_instruction_history(
        _payload(),
        history_dir=tmp_path,
        organization_id="tenant-a",
        project_id="tenant-a",
    )
    database_path = tmp_path / instruction_history.HISTORY_DATABASE_FILENAME
    with connect_database(database_path) as connection:
        row = connection.execute(
            "SELECT record_json FROM instruction_versions WHERE instruction_id = ?",
            (record.instruction_id,),
        ).fetchone()
        tampered = json.loads(str(row["record_json"]))
        tampered["project_id"] = "tenant-b"
        connection.execute(
            "UPDATE instruction_versions SET record_json = ? WHERE instruction_id = ?",
            (json.dumps(tampered), record.instruction_id),
        )

    with pytest.raises(ValueError, match="record scope"):
        instruction_history.list_instruction_history(
            history_dir=tmp_path,
            organization_id="tenant-a",
            project_id="tenant-a",
        )


def test_backup_restore_round_trip_and_safety_backup(tmp_path) -> None:
    history_dir = tmp_path / "history"
    database_path = history_dir / instruction_history.HISTORY_DATABASE_FILENAME
    payload = _payload()
    first = instruction_history.save_instruction_history(payload, history_dir=history_dir)
    backup_path = tmp_path / "backups" / "snapshot.sqlite3"
    backup_database(database_path, backup_path)
    second = instruction_history.save_instruction_history(payload, history_dir=history_dir)
    assert second.version == 2

    safety_path = tmp_path / "backups" / "pre-restore.sqlite3"
    restore_database(backup_path, database_path, safety_backup_path=safety_path)

    restored = instruction_history.list_instruction_history(history_dir=history_dir)
    assert [item.version for item in restored] == [first.version]
    assert verify_database(database_path)["status"] == "ok"
    assert verify_database(safety_path)["instruction_versions"] == 2
    assert oct(backup_path.stat().st_mode & 0o777) == "0o600"


def test_restore_rejects_replacement_without_safety_backup(tmp_path) -> None:
    history_dir = tmp_path / "history"
    database_path = history_dir / instruction_history.HISTORY_DATABASE_FILENAME
    instruction_history.save_instruction_history(_payload(), history_dir=history_dir)
    backup_path = tmp_path / "snapshot.sqlite3"
    backup_database(database_path, backup_path)

    with pytest.raises(ValueError, match="safety backup"):
        restore_database(backup_path, database_path)


def test_database_management_cli_migrate_verify_and_backup(tmp_path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "app.sqlite3"
    backup_path = tmp_path / "backup.sqlite3"
    monkeypatch.setattr(sys, "argv", ["manage_database.py", "migrate", "--database", str(database_path)])
    manage_database.main()
    migrated = json.loads(capsys.readouterr().out)
    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION

    monkeypatch.setattr(sys, "argv", ["manage_database.py", "verify", "--database", str(database_path)])
    manage_database.main()
    verified = json.loads(capsys.readouterr().out)
    assert verified["audit_chain"] == "ok"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "manage_database.py",
            "backup",
            "--database",
            str(database_path),
            "--output",
            str(backup_path),
        ],
    )
    manage_database.main()
    backed_up = json.loads(capsys.readouterr().out)
    assert backed_up["backup"] == str(backup_path)
    assert backup_path.is_file()
