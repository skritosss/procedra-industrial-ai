from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from app.core.authorization import default_project_id
from app.core.settings import get_settings
from app.schemas.admin import AdminAuditEvent, InvitationPublic, ProjectPublic
from app.schemas.auth import UserPublic, UserRole
from app.storage.auth_store import insert_user_record
from app.storage.database import apply_migrations, connect_database


class AdminResourceNotFound(ValueError):
    pass


class AdminConflict(ValueError):
    pass


def append_admin_audit_event(
    connection: sqlite3.Connection,
    *,
    organization_id: str,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, object],
) -> None:
    connection.execute(
        """
        INSERT INTO admin_audit_events (
            event_id, organization_id, actor_user_id, action,
            target_type, target_id, details_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            secrets.token_hex(16),
            organization_id,
            actor_user_id,
            action,
            target_type,
            target_id,
            json.dumps(details, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            datetime.now(UTC).isoformat(),
        ),
    )


def create_invitation(
    organization_id: str,
    actor_user_id: str,
    email: str,
    full_name: str,
    role: UserRole,
    project_ids: list[str],
    *,
    ttl_seconds: int,
    database_path: Path | None = None,
) -> tuple[InvitationPublic, str]:
    if not 300 <= ttl_seconds <= 2_592_000:
        raise ValueError("Invitation TTL must be between 300 and 2592000 seconds")
    path = database_path or get_settings().database_path
    normalized_email = email.strip().lower()
    normalized_name = full_name.strip()
    now = datetime.now(UTC)
    invitation_id = secrets.token_hex(16)
    token = secrets.token_urlsafe(32)
    selected_projects = sorted(set(project_ids) - {default_project_id(organization_id)})
    with closing(connect_database(path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            _require_admin(connection, organization_id, actor_user_id)
            connection.execute(
                """
                UPDATE admin_invitations
                SET revoked_at = ?
                WHERE organization_id = ? AND email = ?
                  AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at <= ?
                """,
                (now.isoformat(), organization_id, normalized_email, now.isoformat()),
            )
            if connection.execute("SELECT 1 FROM users WHERE email = ?", (normalized_email,)).fetchone():
                raise AdminConflict("Account or pending invitation already exists")
            _require_projects(connection, organization_id, selected_projects)
            connection.execute(
                """
                INSERT INTO admin_invitations (
                    invitation_id, organization_id, email, full_name, role,
                    project_ids_json, token_hash, created_by_user_id,
                    created_at, expires_at, accepted_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    invitation_id,
                    organization_id,
                    normalized_email,
                    normalized_name,
                    role,
                    json.dumps(selected_projects, separators=(",", ":")),
                    _hash_token(token),
                    actor_user_id,
                    now.isoformat(),
                    (now + timedelta(seconds=ttl_seconds)).isoformat(),
                ),
            )
            append_admin_audit_event(
                connection,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="invitation.created",
                target_type="invitation",
                target_id=invitation_id,
                details={"email": normalized_email, "role": role, "project_ids": selected_projects},
            )
            row = connection.execute(
                "SELECT * FROM admin_invitations WHERE invitation_id = ?", (invitation_id,)
            ).fetchone()
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise AdminConflict("Account or pending invitation already exists") from exc
        except Exception:
            connection.rollback()
            raise
    if row is None:
        raise RuntimeError("Invitation creation failed")
    return _invitation_from_row(row), token


def list_invitations(
    organization_id: str,
    actor_user_id: str,
    *,
    database_path: Path | None = None,
) -> list[InvitationPublic]:
    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        _require_admin(connection, organization_id, actor_user_id)
        rows = connection.execute(
            "SELECT * FROM admin_invitations WHERE organization_id = ? ORDER BY created_at DESC",
            (organization_id,),
        ).fetchall()
    return [_invitation_from_row(row) for row in rows]


def revoke_invitation(
    organization_id: str,
    actor_user_id: str,
    invitation_id: str,
    *,
    database_path: Path | None = None,
) -> None:
    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            _require_admin(connection, organization_id, actor_user_id)
            row = connection.execute(
                "SELECT * FROM admin_invitations WHERE invitation_id = ? AND organization_id = ?",
                (invitation_id, organization_id),
            ).fetchone()
            if row is None:
                raise AdminResourceNotFound("Invitation not found")
            if row["accepted_at"] is not None:
                raise AdminConflict("Accepted invitation cannot be revoked")
            if row["revoked_at"] is None:
                connection.execute(
                    "UPDATE admin_invitations SET revoked_at = ? WHERE invitation_id = ?",
                    (datetime.now(UTC).isoformat(), invitation_id),
                )
                append_admin_audit_event(
                    connection,
                    organization_id=organization_id,
                    actor_user_id=actor_user_id,
                    action="invitation.revoked",
                    target_type="invitation",
                    target_id=invitation_id,
                    details={"email": str(row["email"])},
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def accept_invitation(
    token: str,
    password: str,
    *,
    database_path: Path | None = None,
) -> UserPublic:
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must contain between 8 and 128 characters")
    now = datetime.now(UTC)
    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM admin_invitations
                WHERE token_hash = ? AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > ?
                """,
                (_hash_token(token), now.isoformat()),
            ).fetchone()
            if row is None:
                raise AdminResourceNotFound("Invitation is invalid or expired")
            organization_id = str(row["organization_id"])
            project_ids = _project_ids(row)
            _require_projects(connection, organization_id, project_ids)
            user = insert_user_record(
                connection,
                str(row["email"]),
                str(row["full_name"]),
                password,
                cast(UserRole, str(row["role"])),
                organization_id,
            )
            for project_id in project_ids:
                connection.execute(
                    """
                    INSERT INTO project_members (organization_id, project_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (organization_id, project_id, user.user_id, now.isoformat()),
                )
            connection.execute(
                "UPDATE admin_invitations SET accepted_at = ? WHERE invitation_id = ?",
                (now.isoformat(), str(row["invitation_id"])),
            )
            append_admin_audit_event(
                connection,
                organization_id=organization_id,
                actor_user_id=user.user_id,
                action="invitation.accepted",
                target_type="user",
                target_id=user.user_id,
                details={"invitation_id": str(row["invitation_id"]), "project_ids": project_ids},
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise AdminConflict("Invitation cannot be accepted") from exc
        except Exception:
            connection.rollback()
            raise
    return user


def list_organization_users(
    organization_id: str,
    actor_user_id: str,
    *,
    database_path: Path | None = None,
) -> list[UserPublic]:
    from app.storage.auth_store import _user_from_row

    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        _require_admin(connection, organization_id, actor_user_id)
        rows = connection.execute(
            "SELECT * FROM users WHERE organization_id = ? ORDER BY created_at",
            (organization_id,),
        ).fetchall()
    return [_user_from_row(row) for row in rows]


def update_organization_user(
    organization_id: str,
    actor_user_id: str,
    target_user_id: str,
    *,
    role: UserRole | None,
    is_active: bool | None,
    database_path: Path | None = None,
) -> UserPublic:
    from app.storage.auth_store import _user_from_row

    path = database_path or get_settings().database_path
    with closing(connect_database(path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            _require_admin(connection, organization_id, actor_user_id)
            row = connection.execute(
                "SELECT * FROM users WHERE user_id = ? AND organization_id = ?",
                (target_user_id, organization_id),
            ).fetchone()
            if row is None:
                raise AdminResourceNotFound("User not found")
            old_role = str(row["role"])
            old_active = bool(row["is_active"])
            new_role = role or cast(UserRole, old_role)
            new_active = old_active if is_active is None else is_active
            if target_user_id == actor_user_id and (new_role != "admin" or not new_active):
                raise AdminConflict("Administrators cannot remove their own active admin access")
            if old_role == "admin" and old_active and (new_role != "admin" or not new_active):
                active_admins = connection.execute(
                    "SELECT COUNT(*) FROM users WHERE organization_id = ? AND role = 'admin' AND is_active = 1",
                    (organization_id,),
                ).fetchone()
                if active_admins is None or int(active_admins[0]) <= 1:
                    raise AdminConflict("The last active administrator cannot be disabled or demoted")
            connection.execute(
                "UPDATE users SET role = ?, is_active = ? WHERE user_id = ?",
                (new_role, int(new_active), target_user_id),
            )
            if new_role != old_role or not new_active:
                connection.execute(
                    "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                    (datetime.now(UTC).isoformat(), target_user_id),
                )
            if new_role != old_role or new_active != old_active:
                append_admin_audit_event(
                    connection,
                    organization_id=organization_id,
                    actor_user_id=actor_user_id,
                    action="user.updated",
                    target_type="user",
                    target_id=target_user_id,
                    details={
                        "old_role": old_role,
                        "new_role": new_role,
                        "old_is_active": old_active,
                        "new_is_active": new_active,
                    },
                )
            updated = connection.execute("SELECT * FROM users WHERE user_id = ?", (target_user_id,)).fetchone()
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    if updated is None:
        raise RuntimeError("User update failed")
    return _user_from_row(updated)


def create_organization_project(
    organization_id: str,
    actor_user_id: str,
    name: str,
    *,
    database_path: Path | None = None,
) -> ProjectPublic:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Project name is required")
    project_id = os.urandom(16).hex()
    now = datetime.now(UTC)
    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            _require_admin(connection, organization_id, actor_user_id)
            connection.execute(
                "INSERT INTO projects (project_id, organization_id, name, is_default, created_at) VALUES (?, ?, ?, 0, ?)",
                (project_id, organization_id, normalized_name, now.isoformat()),
            )
            connection.execute(
                "INSERT INTO project_members (organization_id, project_id, user_id, created_at) VALUES (?, ?, ?, ?)",
                (organization_id, project_id, actor_user_id, now.isoformat()),
            )
            append_admin_audit_event(
                connection,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="project.created",
                target_type="project",
                target_id=project_id,
                details={"name": normalized_name},
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return ProjectPublic(
        project_id=project_id,
        organization_id=organization_id,
        name=normalized_name,
        is_default=False,
        created_at=now,
    )


def list_organization_projects(
    organization_id: str,
    actor_user_id: str,
    *,
    database_path: Path | None = None,
) -> list[ProjectPublic]:
    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        _require_admin(connection, organization_id, actor_user_id)
        rows = connection.execute(
            "SELECT * FROM projects WHERE organization_id = ? ORDER BY is_default DESC, created_at",
            (organization_id,),
        ).fetchall()
    return [_project_from_row(row) for row in rows]


def set_project_membership(
    organization_id: str,
    actor_user_id: str,
    project_id: str,
    target_user_id: str,
    *,
    present: bool,
    database_path: Path | None = None,
) -> bool:
    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            _require_admin(connection, organization_id, actor_user_id)
            _require_projects(connection, organization_id, [project_id])
            user = connection.execute(
                "SELECT 1 FROM users WHERE user_id = ? AND organization_id = ?",
                (target_user_id, organization_id),
            ).fetchone()
            if user is None:
                raise AdminResourceNotFound("User not found")
            if not present and project_id == default_project_id(organization_id):
                raise AdminConflict("Users cannot be removed from the organization default project")
            if present:
                result = connection.execute(
                    "INSERT OR IGNORE INTO project_members (organization_id, project_id, user_id, created_at) VALUES (?, ?, ?, ?)",
                    (organization_id, project_id, target_user_id, datetime.now(UTC).isoformat()),
                )
            else:
                result = connection.execute(
                    "DELETE FROM project_members WHERE organization_id = ? AND project_id = ? AND user_id = ?",
                    (organization_id, project_id, target_user_id),
                )
            changed = result.rowcount > 0
            if changed:
                append_admin_audit_event(
                    connection,
                    organization_id=organization_id,
                    actor_user_id=actor_user_id,
                    action="project.member_added" if present else "project.member_removed",
                    target_type="user",
                    target_id=target_user_id,
                    details={"project_id": project_id},
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return changed


def list_project_members(
    organization_id: str,
    actor_user_id: str,
    project_id: str,
    *,
    database_path: Path | None = None,
) -> list[UserPublic]:
    from app.storage.auth_store import _user_from_row

    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        _require_admin(connection, organization_id, actor_user_id)
        _require_projects(connection, organization_id, [project_id])
        rows = connection.execute(
            """
            SELECT u.*
            FROM project_members pm
            JOIN users u ON u.user_id = pm.user_id AND u.organization_id = pm.organization_id
            WHERE pm.organization_id = ? AND pm.project_id = ?
            ORDER BY u.created_at
            """,
            (organization_id, project_id),
        ).fetchall()
    return [_user_from_row(row) for row in rows]


def list_admin_audit_events(
    organization_id: str,
    actor_user_id: str,
    *,
    limit: int = 200,
    database_path: Path | None = None,
) -> list[AdminAuditEvent]:
    with closing(connect_database(database_path or get_settings().database_path)) as connection:
        apply_migrations(connection)
        _require_admin(connection, organization_id, actor_user_id)
        rows = connection.execute(
            "SELECT * FROM admin_audit_events WHERE organization_id = ? ORDER BY created_at DESC LIMIT ?",
            (organization_id, limit),
        ).fetchall()
    return [
        AdminAuditEvent(
            event_id=str(row["event_id"]),
            organization_id=str(row["organization_id"]),
            actor_user_id=str(row["actor_user_id"]),
            action=str(row["action"]),
            target_type=str(row["target_type"]),
            target_id=str(row["target_id"]),
            details=cast(dict[str, object], json.loads(str(row["details_json"]))),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
        for row in rows
    ]


def _require_admin(connection: sqlite3.Connection, organization_id: str, actor_user_id: str) -> None:
    row = connection.execute(
        """
        SELECT 1 FROM users
        WHERE user_id = ? AND organization_id = ? AND role = 'admin' AND is_active = 1
        """,
        (actor_user_id, organization_id),
    ).fetchone()
    if row is None:
        raise AdminResourceNotFound("Administrative resource not found")


def _require_projects(connection: sqlite3.Connection, organization_id: str, project_ids: list[str]) -> None:
    for project_id in project_ids:
        if connection.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND organization_id = ?",
            (project_id, organization_id),
        ).fetchone() is None:
            raise AdminResourceNotFound("Project not found")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _project_ids(row: sqlite3.Row) -> list[str]:
    value: Any = json.loads(str(row["project_ids_json"]))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Invitation project membership is invalid")
    return list(value)


def _invitation_from_row(row: sqlite3.Row) -> InvitationPublic:
    return InvitationPublic(
        invitation_id=str(row["invitation_id"]),
        email=str(row["email"]),
        full_name=str(row["full_name"]),
        role=cast(UserRole, str(row["role"])),
        project_ids=_project_ids(row),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        expires_at=datetime.fromisoformat(str(row["expires_at"])),
        accepted_at=datetime.fromisoformat(str(row["accepted_at"])) if row["accepted_at"] else None,
        revoked_at=datetime.fromisoformat(str(row["revoked_at"])) if row["revoked_at"] else None,
    )


def _project_from_row(row: sqlite3.Row) -> ProjectPublic:
    return ProjectPublic(
        project_id=str(row["project_id"]),
        organization_id=str(row["organization_id"]),
        name=str(row["name"]),
        is_default=bool(row["is_default"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )
