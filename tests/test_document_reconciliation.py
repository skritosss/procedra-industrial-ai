import json
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.authorization import get_resource_ownership, project_storage_path
from app.core.authorization import register_resource_ownership
from app.storage.auth_store import create_organization, create_user
from app.storage.document_reconciliation import reconcile_document_ownership
from scripts import reconcile_document_ownership as reconciliation_cli


def _write_document(
    root,
    organization_id: str,
    project_id: str,
    document_id: str,
    *,
    metadata_organization: str | None = None,
    metadata_project: str | None = None,
    owner_user_id: str | None = None,
):
    path = project_storage_path(root, organization_id, project_id) / f"{document_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata_organization = organization_id if metadata_organization is None else metadata_organization
    metadata_project = project_id if metadata_project is None else metadata_project
    path.write_text(
        "\n".join(
            (
                "# Controlled document",
                "",
                "Original filename: controlled.md",
                "Source kind: uploaded enterprise document",
                "",
                f"Organization ID: {metadata_organization}",
                f"Project ID: {metadata_project}",
                f"Owner user ID: {owner_user_id or ''}",
                "",
                "Verified procedure text.",
            )
        ),
        encoding="utf-8",
    )
    return path


def test_reconciliation_is_dry_run_by_default_and_apply_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    organization_id = create_organization("Reconciliation", database_path=database_path)
    user = create_user(
        "reconciliation@example.com",
        "Reconciliation Owner",
        "strong-reconciliation-password",
        organization_id=organization_id,
        database_path=database_path,
    )
    _write_document(
        documents_root,
        organization_id,
        organization_id,
        "controlled-document",
        owner_user_id=user.user_id,
    )

    plan = reconcile_document_ownership(
        database_path=database_path,
        documents_root=documents_root,
    )

    assert plan.dry_run is True
    assert plan.candidates == 1
    assert plan.registered == 0
    assert get_resource_ownership(
        organization_id,
        "document",
        "controlled-document",
        database_path=database_path,
    ) is None

    applied = reconcile_document_ownership(
        database_path=database_path,
        documents_root=documents_root,
        apply=True,
    )
    repeated = reconcile_document_ownership(
        database_path=database_path,
        documents_root=documents_root,
        apply=True,
    )

    assert applied.registered == 1
    assert applied.blocked_by_issues is False
    assert repeated.registered == 0
    assert repeated.candidates == 0
    assert repeated.already_registered == 1


def test_reconciliation_rejects_scope_mismatch_and_applies_nothing(tmp_path) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    organization_id = create_organization("Scope", database_path=database_path)
    _write_document(documents_root, organization_id, organization_id, "valid")
    _write_document(
        documents_root,
        organization_id,
        organization_id,
        "mismatched",
        metadata_organization="other-organization",
    )

    result = reconcile_document_ownership(
        database_path=database_path,
        documents_root=documents_root,
        apply=True,
    )

    assert result.blocked_by_issues is True
    assert result.candidates == 1
    assert result.registered == 0
    assert [issue.category for issue in result.issues] == ["scope_metadata_mismatch"]
    assert get_resource_ownership(
        organization_id,
        "document",
        "valid",
        database_path=database_path,
    ) is None


def test_reconciliation_rejects_owner_from_another_organization(tmp_path) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    organization_a = create_organization("Owner A", database_path=database_path)
    organization_b = create_organization("Owner B", database_path=database_path)
    user_b = create_user(
        "owner-b@example.com",
        "Owner B",
        "strong-owner-password-b",
        organization_id=organization_b,
        database_path=database_path,
    )
    _write_document(
        documents_root,
        organization_a,
        organization_a,
        "wrong-owner",
        owner_user_id=user_b.user_id,
    )

    result = reconcile_document_ownership(
        database_path=database_path,
        documents_root=documents_root,
    )

    assert result.candidates == 0
    assert [issue.category for issue in result.issues] == ["owner_not_in_organization"]


def test_reconciliation_rejects_document_outside_known_project_paths(tmp_path) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    create_organization("Known", database_path=database_path)
    unknown = documents_root / "unknown-organization" / "orphan.txt"
    unknown.parent.mkdir(parents=True)
    unknown.write_text("# Unmapped document", encoding="utf-8")

    result = reconcile_document_ownership(
        database_path=database_path,
        documents_root=documents_root,
    )

    assert result.scanned_files == 1
    assert [issue.category for issue in result.issues] == ["unmapped_document_path"]


def test_concurrent_apply_registers_document_once(tmp_path) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    organization_id = create_organization("Concurrent", database_path=database_path)
    _write_document(documents_root, organization_id, organization_id, "concurrent-document")

    def apply_plan():
        return reconcile_document_ownership(
            database_path=database_path,
            documents_root=documents_root,
            apply=True,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: apply_plan(), range(2)))

    assert sorted(result.registered for result in results) == [0, 1]
    assert sorted(result.already_registered for result in results) == [0, 1]


def test_reconciliation_reports_database_ownership_without_file(tmp_path) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    organization_id = create_organization("Missing file", database_path=database_path)
    register_resource_ownership(
        organization_id,
        organization_id,
        "document",
        "missing-document",
        None,
        database_path=database_path,
    )

    result = reconcile_document_ownership(
        database_path=database_path,
        documents_root=documents_root,
    )

    assert result.blocked_by_issues is True
    assert [issue.category for issue in result.issues] == ["ownership_without_file"]


def test_reconciliation_cli_defaults_to_dry_run(tmp_path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    organization_id = create_organization("CLI", database_path=database_path)
    _write_document(documents_root, organization_id, organization_id, "cli-document")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_document_ownership.py",
            "--database",
            str(database_path),
            "--documents-root",
            str(documents_root),
        ],
    )

    reconciliation_cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["dry_run"] is True
    assert payload["candidates"] == 1
    assert payload["registered"] == 0


def test_reconciliation_cli_exits_nonzero_on_tenant_issue(tmp_path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "app.sqlite3"
    documents_root = tmp_path / "documents"
    organization_id = create_organization("CLI issue", database_path=database_path)
    _write_document(
        documents_root,
        organization_id,
        organization_id,
        "bad-scope",
        metadata_project="different-project",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_document_ownership.py",
            "--database",
            str(database_path),
            "--documents-root",
            str(documents_root),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        reconciliation_cli.main()

    assert exc_info.value.code == 2
    assert json.loads(capsys.readouterr().out)["blocked_by_issues"] is True
