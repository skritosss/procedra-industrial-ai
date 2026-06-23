from __future__ import annotations

import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from fastapi import HTTPException, Request

from app.core.organization import LEGACY_ORGANIZATION_ID, organization_storage_path
from app.core.settings import get_settings
from app.schemas.auth import UserPublic, UserRole
from app.storage.database import apply_migrations, connect_database


Permission = Literal[
    "document:read",
    "document:upload",
    "instruction:read",
    "instruction:create",
    "workflow:review",
    "workflow:approve",
    "execution:read",
    "execution:create",
    "video:read",
    "video:create",
    "project:admin",
]
ResourceType = Literal["document", "instruction", "video"]
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ALL_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        "document:read",
        "document:upload",
        "instruction:read",
        "instruction:create",
        "workflow:review",
        "workflow:approve",
        "execution:read",
        "execution:create",
        "video:read",
        "video:create",
        "project:admin",
    }
)


ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    "operator": frozenset(
        {
            "document:read",
            "instruction:read",
            "instruction:create",
            "execution:read",
            "execution:create",
            "video:read",
            "video:create",
        }
    ),
    "master": frozenset(
        {
            "document:read",
            "document:upload",
            "instruction:read",
            "instruction:create",
            "workflow:review",
            "execution:read",
            "execution:create",
            "video:read",
            "video:create",
        }
    ),
    "technologist": frozenset(),
    "safety": frozenset(),
    "quality": frozenset(),
    "admin": frozenset(),
}
_REVIEWER_PERMISSIONS = cast(
    frozenset[Permission],
    ROLE_PERMISSIONS["master"] | {"workflow:approve"},
)
for _role in ("technologist", "safety", "quality"):
    ROLE_PERMISSIONS[cast(UserRole, _role)] = _REVIEWER_PERMISSIONS
ROLE_PERMISSIONS["admin"] = ALL_PERMISSIONS


@dataclass(frozen=True)
class AccessContext:
    user: UserPublic | None
    organization_id: str
    project_id: str


@dataclass(frozen=True)
class ResourceOwnership:
    organization_id: str
    project_id: str
    resource_type: ResourceType
    resource_id: str
    owner_user_id: str | None


def default_project_id(organization_id: str) -> str:
    return organization_id


def project_storage_path(root: Path, organization_id: str, project_id: str) -> Path:
    organization_root = organization_storage_path(root, organization_id)
    if project_id == default_project_id(organization_id):
        return organization_root
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("Invalid project identifier")
    return organization_root / project_id


def require_permission(request: Request, permission: Permission, settings=None) -> AccessContext:
    user = getattr(request.state, "current_user", None)
    settings = settings or get_settings()
    if not isinstance(user, UserPublic):
        if getattr(settings, "deployment_mode", "demo") == "production":
            raise HTTPException(status_code=401, detail="Authenticated user session is required")
        context = AccessContext(
            user=None,
            organization_id=LEGACY_ORGANIZATION_ID,
            project_id=default_project_id(LEGACY_ORGANIZATION_ID),
        )
        _bind_request_context(request, context)
        return context
    if permission not in ROLE_PERMISSIONS[user.role]:
        raise HTTPException(status_code=403, detail=f"Role {user.role} is not allowed to perform {permission}")
    project_id = request.headers.get("X-Project-ID", "").strip() or user.project_id
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise HTTPException(status_code=400, detail="Invalid project identifier")
    if not user_has_project_access(user, project_id, settings.database_path):
        raise HTTPException(status_code=404, detail="Project not found")
    context = AccessContext(user=user, organization_id=user.organization_id, project_id=project_id)
    _bind_request_context(request, context)
    return context


def _bind_request_context(request: Request, context: AccessContext) -> None:
    request.state.organization_id = context.organization_id
    request.state.project_id = context.project_id


def require_resource_access(
    context: AccessContext,
    resource_type: ResourceType,
    resource_id: str,
    *,
    database_path: Path | None = None,
) -> ResourceOwnership:
    ownership = get_resource_ownership(
        context.organization_id,
        resource_type,
        resource_id,
        database_path=database_path,
    )
    if ownership is None or ownership.project_id != context.project_id:
        raise HTTPException(status_code=404, detail="Resource not found")
    return ownership


def user_has_project_access(user: UserPublic, project_id: str, database_path: Path) -> bool:
    with closing(connect_database(database_path)) as connection:
        apply_migrations(connection)
        row = connection.execute(
            """
            SELECT 1
            FROM project_members pm
            JOIN projects p
              ON p.project_id = pm.project_id AND p.organization_id = pm.organization_id
            JOIN users u
              ON u.user_id = pm.user_id AND u.organization_id = pm.organization_id
            WHERE pm.organization_id = ? AND pm.project_id = ? AND pm.user_id = ?
            """,
            (user.organization_id, project_id, user.user_id),
        ).fetchone()
    return row is not None


def create_project(
    organization_id: str,
    name: str,
    creator_user_id: str,
    *,
    database_path: Path | None = None,
) -> str:
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 120:
        raise ValueError("Project name must contain between 1 and 120 characters")
    project_id = os.urandom(16).hex()
    path = database_path or get_settings().database_path
    with closing(connect_database(path)) as connection:
        apply_migrations(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            organization = connection.execute(
                "SELECT 1 FROM organizations WHERE organization_id = ?",
                (organization_id,),
            ).fetchone()
            user = connection.execute(
                "SELECT 1 FROM users WHERE user_id = ? AND organization_id = ?",
                (creator_user_id, organization_id),
            ).fetchone()
            if not organization or not user:
                raise ValueError("Organization or project creator does not exist")
            connection.execute(
                """
                INSERT INTO projects (project_id, organization_id, name, is_default, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (project_id, organization_id, normalized_name, datetime.now(UTC).isoformat()),
            )
            connection.execute(
                """
                INSERT INTO project_members (organization_id, project_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (organization_id, project_id, creator_user_id, datetime.now(UTC).isoformat()),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return project_id


def add_project_member(
    organization_id: str,
    project_id: str,
    user_id: str,
    *,
    database_path: Path | None = None,
) -> None:
    path = database_path or get_settings().database_path
    with closing(connect_database(path)) as connection:
        apply_migrations(connection)
        project = connection.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND organization_id = ?",
            (project_id, organization_id),
        ).fetchone()
        user = connection.execute(
            "SELECT 1 FROM users WHERE user_id = ? AND organization_id = ?",
            (user_id, organization_id),
        ).fetchone()
        if not project or not user:
            raise ValueError("Project or user does not exist in the organization")
        connection.execute(
            """
            INSERT OR IGNORE INTO project_members (organization_id, project_id, user_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (organization_id, project_id, user_id, datetime.now(UTC).isoformat()),
        )
        connection.commit()


def register_resource_ownership(
    organization_id: str,
    project_id: str,
    resource_type: ResourceType,
    resource_id: str,
    owner_user_id: str | None,
    *,
    database_path: Path | None = None,
    connection: sqlite3.Connection | None = None,
) -> ResourceOwnership:
    owns_connection = connection is None
    active = connection or connect_database(database_path or get_settings().database_path)
    try:
        if owns_connection:
            apply_migrations(active)
        organization_exists = active.execute(
            "SELECT 1 FROM organizations WHERE organization_id = ?",
            (organization_id,),
        ).fetchone()
        if organization_exists is None and owns_connection:
            raise ValueError("Organization does not exist")
        if organization_exists is not None and owner_user_id is not None:
            owner_exists = active.execute(
                "SELECT 1 FROM users WHERE user_id = ? AND organization_id = ?",
                (owner_user_id, organization_id),
            ).fetchone()
            organization_has_users = active.execute(
                "SELECT 1 FROM users WHERE organization_id = ? LIMIT 1",
                (organization_id,),
            ).fetchone()
            if owner_exists is None and (owns_connection or organization_has_users is not None):
                raise ValueError("Resource owner does not exist in the organization")
        _ensure_project(active, organization_id, project_id)
        active.execute(
            """
            INSERT INTO resource_ownership (
                organization_id, project_id, resource_type, resource_id, owner_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (organization_id, resource_type, resource_id) DO NOTHING
            """,
            (
                organization_id,
                project_id,
                resource_type,
                resource_id,
                owner_user_id,
                datetime.now(UTC).isoformat(),
            ),
        )
        row = active.execute(
            """
            SELECT organization_id, project_id, resource_type, resource_id, owner_user_id
            FROM resource_ownership
            WHERE organization_id = ? AND resource_type = ? AND resource_id = ?
            """,
            (organization_id, resource_type, resource_id),
        ).fetchone()
        if row is None:
            raise ValueError("Resource ownership could not be registered")
        if str(row["project_id"]) != project_id:
            raise ValueError("Resource is already assigned to another project")
        if owns_connection:
            active.commit()
        return _ownership_from_row(row)
    finally:
        if owns_connection:
            active.close()


def get_resource_ownership(
    organization_id: str,
    resource_type: ResourceType,
    resource_id: str,
    *,
    database_path: Path | None = None,
) -> ResourceOwnership | None:
    path = database_path or get_settings().database_path
    with closing(connect_database(path)) as connection:
        apply_migrations(connection)
        row = connection.execute(
            """
            SELECT organization_id, project_id, resource_type, resource_id, owner_user_id
            FROM resource_ownership
            WHERE organization_id = ? AND resource_type = ? AND resource_id = ?
            """,
            (organization_id, resource_type, resource_id),
        ).fetchone()
    return _ownership_from_row(row) if row is not None else None


def list_project_resource_ownerships(
    organization_id: str,
    project_id: str,
    resource_type: ResourceType,
    *,
    database_path: Path | None = None,
) -> dict[str, ResourceOwnership]:
    path = database_path or get_settings().database_path
    with closing(connect_database(path)) as connection:
        apply_migrations(connection)
        rows = connection.execute(
            """
            SELECT organization_id, project_id, resource_type, resource_id, owner_user_id
            FROM resource_ownership
            WHERE organization_id = ? AND project_id = ? AND resource_type = ?
            """,
            (organization_id, project_id, resource_type),
        ).fetchall()
    ownerships = (_ownership_from_row(row) for row in rows)
    return {ownership.resource_id: ownership for ownership in ownerships}


def _ensure_project(connection: sqlite3.Connection, organization_id: str, project_id: str) -> None:
    row = connection.execute(
        "SELECT 1 FROM projects WHERE project_id = ? AND organization_id = ?",
        (project_id, organization_id),
    ).fetchone()
    if row is None and project_id == default_project_id(organization_id):
        connection.execute(
            """
            INSERT OR IGNORE INTO projects (project_id, organization_id, name, is_default, created_at)
            VALUES (?, ?, 'Default Project', 1, ?)
            """,
            (project_id, organization_id, datetime.now(UTC).isoformat()),
        )
        row = connection.execute(
            "SELECT 1 FROM projects WHERE project_id = ? AND organization_id = ?",
            (project_id, organization_id),
        ).fetchone()
    if row is None:
        raise ValueError("Project does not exist in the organization")


def _ownership_from_row(row: sqlite3.Row) -> ResourceOwnership:
    return ResourceOwnership(
        organization_id=str(row["organization_id"]),
        project_id=str(row["project_id"]),
        resource_type=cast(ResourceType, str(row["resource_type"])),
        resource_id=str(row["resource_id"]),
        owner_user_id=str(row["owner_user_id"]) if row["owner_user_id"] else None,
    )
