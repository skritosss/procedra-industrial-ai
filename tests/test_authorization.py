import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.authorization import (
    ROLE_PERMISSIONS,
    add_project_member,
    create_project,
    register_resource_ownership,
    require_permission,
    require_resource_access,
)
from app.core.settings import get_settings
from app.storage.auth_store import create_organization, create_user
from app.storage.database import connect_database, verify_database


def _request(user, project_id: str | None = None) -> Request:
    headers = [] if project_id is None else [(b"x-project-id", project_id.encode())]
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": headers})
    request.state.current_user = user
    return request


def _settings(database_path: Path):
    return get_settings().model_copy(update={"deployment_mode": "production", "database_path": database_path})


def test_permission_matrix_has_explicit_least_privilege_boundaries() -> None:
    assert "document:upload" not in ROLE_PERMISSIONS["operator"]
    assert "workflow:review" not in ROLE_PERMISSIONS["operator"]
    assert "workflow:approve" not in ROLE_PERMISSIONS["master"]
    for role in ("technologist", "safety", "quality", "admin"):
        assert "workflow:approve" in ROLE_PERMISSIONS[role]
    assert ROLE_PERMISSIONS["admin"] == set().union(*ROLE_PERMISSIONS.values())


@pytest.mark.parametrize("role", ["operator", "master"])
def test_route_permissions_reject_role_escalation(tmp_path, role) -> None:
    database_path = tmp_path / f"{role}.sqlite3"
    organization_id = create_organization("Permission Test", database_path=database_path)
    user = create_user(
        f"{role}@example.com",
        f"{role.title()} User",
        "strong-password-1",
        role=role,
        organization_id=organization_id,
        database_path=database_path,
    )
    settings = _settings(database_path)

    forbidden = "document:upload" if role == "operator" else "workflow:approve"
    with pytest.raises(HTTPException) as exc:
        require_permission(_request(user), forbidden, settings)

    assert exc.value.status_code == 403


def test_project_membership_and_resource_access_are_non_enumerable(tmp_path) -> None:
    database_path = tmp_path / "projects.sqlite3"
    organization_id = create_organization("Projects", database_path=database_path)
    owner = create_user(
        "owner@example.com",
        "Project Owner",
        "strong-password-1",
        role="master",
        organization_id=organization_id,
        database_path=database_path,
    )
    outsider = create_user(
        "outsider@example.com",
        "Project Outsider",
        "strong-password-1",
        role="master",
        organization_id=organization_id,
        database_path=database_path,
    )
    project_id = create_project(
        organization_id,
        "Restricted Project",
        owner.user_id,
        database_path=database_path,
    )
    settings = _settings(database_path)

    owner_context = require_permission(_request(owner, project_id), "document:upload", settings)
    register_resource_ownership(
        organization_id,
        project_id,
        "document",
        "restricted-manual",
        owner.user_id,
        database_path=database_path,
    )
    assert require_resource_access(
        owner_context,
        "document",
        "restricted-manual",
        database_path=database_path,
    ).owner_user_id == owner.user_id

    with pytest.raises(HTTPException) as exc:
        require_permission(_request(outsider, project_id), "document:read", settings)
    assert exc.value.status_code == 404

    add_project_member(
        organization_id,
        project_id,
        outsider.user_id,
        database_path=database_path,
    )
    outsider_context = require_permission(_request(outsider, project_id), "document:read", settings)
    assert require_resource_access(
        outsider_context,
        "document",
        "restricted-manual",
        database_path=database_path,
    ).project_id == project_id

    default_context = require_permission(_request(outsider), "document:read", settings)
    with pytest.raises(HTTPException) as exc:
        require_resource_access(
            default_context,
            "document",
            "restricted-manual",
            database_path=database_path,
        )
    assert exc.value.status_code == 404


def test_cross_organization_project_id_is_hidden(tmp_path) -> None:
    database_path = tmp_path / "tenants.sqlite3"
    organization_a = create_organization("Tenant A", database_path=database_path)
    organization_b = create_organization("Tenant B", database_path=database_path)
    user_a = create_user(
        "a@example.com",
        "Tenant A User",
        "strong-password-1",
        organization_id=organization_a,
        database_path=database_path,
    )
    user_b = create_user(
        "b@example.com",
        "Tenant B User",
        "strong-password-1",
        organization_id=organization_b,
        database_path=database_path,
    )
    project_b = create_project(
        organization_b,
        "Tenant B Private",
        user_b.user_id,
        database_path=database_path,
    )

    with pytest.raises(HTTPException) as exc:
        require_permission(_request(user_a, project_b), "document:read", _settings(database_path))
    assert exc.value.status_code == 404


def test_default_project_access_requires_current_membership(tmp_path) -> None:
    database_path = tmp_path / "revoked.sqlite3"
    organization_id = create_organization("Revoked Membership", database_path=database_path)
    user = create_user(
        "revoked@example.com",
        "Revoked User",
        "strong-password-1",
        organization_id=organization_id,
        database_path=database_path,
    )
    with connect_database(database_path) as connection:
        connection.execute(
            "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
            (organization_id, user.user_id),
        )

    with pytest.raises(HTTPException) as exc:
        require_permission(_request(user), "document:read", _settings(database_path))
    assert exc.value.status_code == 404


def test_database_rejects_mismatched_cross_tenant_membership_row(tmp_path) -> None:
    database_path = tmp_path / "mismatch.sqlite3"
    organization_a = create_organization("Mismatch A", database_path=database_path)
    organization_b = create_organization("Mismatch B", database_path=database_path)
    user_a = create_user(
        "mismatch-a@example.com",
        "Mismatch User A",
        "strong-password-1",
        organization_id=organization_a,
        database_path=database_path,
    )
    user_b = create_user(
        "mismatch-b@example.com",
        "Mismatch User B",
        "strong-password-1",
        organization_id=organization_b,
        database_path=database_path,
    )
    project_b = create_project(
        organization_b,
        "Mismatch Private B",
        user_b.user_id,
        database_path=database_path,
    )
    with connect_database(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                """
                INSERT INTO project_members (organization_id, project_id, user_id, created_at)
                VALUES (?, ?, ?, '2026-06-19T00:00:00+00:00')
                """,
                (organization_a, project_b, user_a.user_id),
            )
        connection.rollback()

    with pytest.raises(HTTPException) as exc:
        require_permission(_request(user_a, project_b), "document:read", _settings(database_path))
    assert exc.value.status_code == 404
    assert verify_database(database_path)["authorization_integrity"] == "ok"


def test_database_rejects_cross_tenant_resource_project_and_owner(tmp_path) -> None:
    database_path = tmp_path / "resource-mismatch.sqlite3"
    organization_a = create_organization("Resource A", database_path=database_path)
    organization_b = create_organization("Resource B", database_path=database_path)
    user_a = create_user(
        "resource-a@example.com",
        "Resource User A",
        "strong-password-1",
        organization_id=organization_a,
        database_path=database_path,
    )
    user_b = create_user(
        "resource-b@example.com",
        "Resource User B",
        "strong-password-1",
        organization_id=organization_b,
        database_path=database_path,
    )
    project_b = create_project(
        organization_b,
        "Resource Project B",
        user_b.user_id,
        database_path=database_path,
    )
    with connect_database(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                """
                INSERT INTO resource_ownership (
                    organization_id, project_id, resource_type, resource_id, owner_user_id, created_at
                ) VALUES (?, ?, 'document', 'wrong-project', ?, '2026-06-20T00:00:00+00:00')
                """,
                (organization_a, project_b, user_a.user_id),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                """
                INSERT INTO resource_ownership (
                    organization_id, project_id, resource_type, resource_id, owner_user_id, created_at
                ) VALUES (?, ?, 'document', 'wrong-owner', ?, '2026-06-20T00:00:00+00:00')
                """,
                (organization_a, organization_a, user_b.user_id),
            )
        connection.rollback()

    assert verify_database(database_path)["authorization_integrity"] == "ok"


@pytest.mark.parametrize("name", ["", " ", "x" * 121])
def test_project_name_is_bounded(tmp_path, name) -> None:
    database_path = tmp_path / "names.sqlite3"
    organization_id = create_organization("Names", database_path=database_path)
    user = create_user(
        "names@example.com",
        "Names User",
        "strong-password-1",
        organization_id=organization_id,
        database_path=database_path,
    )

    with pytest.raises(ValueError, match="Project name"):
        create_project(
            organization_id,
            name,
            user.user_id,
            database_path=database_path,
        )


def test_resource_owner_must_belong_to_organization(tmp_path) -> None:
    database_path = tmp_path / "owners.sqlite3"
    organization_id = create_organization("Owners", database_path=database_path)

    with pytest.raises(ValueError, match="owner does not exist"):
        register_resource_ownership(
            organization_id,
            organization_id,
            "document",
            "manual",
            "missing-user",
            database_path=database_path,
        )
