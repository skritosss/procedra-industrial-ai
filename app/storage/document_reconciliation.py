from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.authorization import project_storage_path
from app.core.organization import LEGACY_ORGANIZATION_ID
from app.storage.database import apply_migrations, connect_database


@dataclass(frozen=True)
class ReconciliationIssue:
    category: str
    artifact: str


@dataclass(frozen=True)
class DocumentOwnershipReconciliation:
    dry_run: bool
    blocked_by_issues: bool
    scanned_files: int
    candidates: int
    registered: int
    already_registered: int
    rejected: int
    documents_root: str
    issues: tuple[ReconciliationIssue, ...]

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["issues"] = [asdict(issue) for issue in self.issues]
        return result


@dataclass(frozen=True)
class _Candidate:
    organization_id: str
    project_id: str
    resource_id: str
    owner_user_id: str | None


def reconcile_document_ownership(
    *,
    database_path: Path,
    documents_root: Path,
    apply: bool = False,
) -> DocumentOwnershipReconciliation:
    root = documents_root.resolve(strict=False)
    with connect_database(database_path) as connection:
        apply_migrations(connection)
        if apply:
            connection.execute("BEGIN IMMEDIATE")
        try:
            candidates, already_registered, scanned_files, issues = _build_plan(connection, root)
            if apply and not issues:
                now = datetime.now(UTC).isoformat()
                connection.executemany(
                    """
                    INSERT INTO resource_ownership (
                        organization_id, project_id, resource_type,
                        resource_id, owner_user_id, created_at
                    ) VALUES (?, ?, 'document', ?, ?, ?)
                    """,
                    [
                        (
                            candidate.organization_id,
                            candidate.project_id,
                            candidate.resource_id,
                            candidate.owner_user_id,
                            now,
                        )
                        for candidate in candidates
                    ],
                )
                connection.commit()
            elif apply:
                connection.rollback()
        except Exception:
            if apply:
                connection.rollback()
            raise
    return DocumentOwnershipReconciliation(
        dry_run=not apply,
        blocked_by_issues=bool(issues),
        scanned_files=scanned_files,
        candidates=len(candidates),
        registered=len(candidates) if apply and not issues else 0,
        already_registered=already_registered,
        rejected=len(issues),
        documents_root=str(root),
        issues=tuple(issues),
    )


def _build_plan(
    connection: sqlite3.Connection,
    root: Path,
) -> tuple[list[_Candidate], int, int, list[ReconciliationIssue]]:
    projects = connection.execute(
        "SELECT organization_id, project_id FROM projects ORDER BY organization_id, project_id"
    ).fetchall()
    existing_rows = connection.execute(
        """
        SELECT organization_id, project_id, resource_id, owner_user_id
        FROM resource_ownership
        WHERE resource_type = 'document'
        """
    ).fetchall()
    existing = {
        (str(row["organization_id"]), str(row["resource_id"])): (
            str(row["project_id"]),
            str(row["owner_user_id"]) if row["owner_user_id"] else None,
        )
        for row in existing_rows
    }
    candidates: list[_Candidate] = []
    issues: list[ReconciliationIssue] = []
    already_registered = 0
    scanned_files = 0
    seen_paths: set[Path] = set()
    seen_resources: set[tuple[str, str]] = set()

    for project in projects:
        organization_id = str(project["organization_id"])
        project_id = str(project["project_id"])
        document_dir = project_storage_path(root, organization_id, project_id)
        paths = sorted(document_dir.glob("*.txt")) if document_dir.is_dir() else ()
        for path in paths:
            if path in seen_paths:
                continue
            seen_paths.add(path)
            scanned_files += 1
            seen_resources.add((organization_id, path.stem))
            artifact = _artifact_name(path, root)
            if path.is_symlink() or not path.is_file():
                issues.append(ReconciliationIssue("unsupported_artifact", artifact))
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                issues.append(ReconciliationIssue("unreadable_document", artifact))
                continue
            metadata_organization = _metadata_value(text, "Organization ID")
            metadata_project = _metadata_value(text, "Project ID")
            owner_user_id = _metadata_value(text, "Owner user ID")
            if (metadata_organization is None) != (metadata_project is None):
                issues.append(ReconciliationIssue("incomplete_scope_metadata", artifact))
                continue
            if metadata_organization is None and organization_id != LEGACY_ORGANIZATION_ID:
                issues.append(ReconciliationIssue("missing_scope_metadata", artifact))
                continue
            if metadata_organization is not None and (
                metadata_organization != organization_id or metadata_project != project_id
            ):
                issues.append(ReconciliationIssue("scope_metadata_mismatch", artifact))
                continue
            if owner_user_id is not None:
                owner = connection.execute(
                    "SELECT 1 FROM users WHERE organization_id = ? AND user_id = ?",
                    (organization_id, owner_user_id),
                ).fetchone()
                if owner is None:
                    issues.append(ReconciliationIssue("owner_not_in_organization", artifact))
                    continue
            resource_id = path.stem
            current = existing.get((organization_id, resource_id))
            if current is not None:
                if current != (project_id, owner_user_id):
                    issues.append(ReconciliationIssue("ownership_conflict", artifact))
                else:
                    already_registered += 1
                continue
            candidates.append(
                _Candidate(
                    organization_id=organization_id,
                    project_id=project_id,
                    resource_id=resource_id,
                    owner_user_id=owner_user_id,
                )
            )
    if root.is_dir():
        for path in sorted(root.rglob("*.txt")):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            scanned_files += 1
            issues.append(ReconciliationIssue("unmapped_document_path", _artifact_name(path, root)))
    projects_by_id = {
        (str(project["organization_id"]), str(project["project_id"]))
        for project in projects
    }
    for (organization_id, resource_id), (project_id, _) in sorted(existing.items()):
        if (organization_id, resource_id) in seen_resources:
            continue
        if (organization_id, project_id) not in projects_by_id:
            issues.append(ReconciliationIssue("ownership_project_missing", resource_id))
            continue
        expected = project_storage_path(root, organization_id, project_id) / f"{resource_id}.txt"
        issues.append(ReconciliationIssue("ownership_without_file", _artifact_name(expected, root)))
    return candidates, already_registered, scanned_files, issues


def _metadata_value(text: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in text.splitlines()[:8]:
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            return value or None
    return None


def _artifact_name(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
