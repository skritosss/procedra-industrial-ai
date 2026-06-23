import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app
from app.storage.admin_store import (
    AdminConflict,
    AdminResourceNotFound,
    accept_invitation,
    create_invitation,
)
from app.storage.auth_store import create_organization, create_session, create_user
from app.storage.database import connect_database, verify_database


def _production_client(tmp_path, monkeypatch):
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "admin-lifecycle-bootstrap-token-32-plus",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": tmp_path / "admin.sqlite3",
        }
    )
    for target in (
        "app.api.auth.get_settings",
        "app.api.admin.get_settings",
        "app.api.documents.get_settings",
        "app.core.security.get_settings",
        "app.storage.auth_store.get_settings",
        "app.storage.admin_store.get_settings",
    ):
        monkeypatch.setattr(target, lambda: settings)
    return TestClient(app), settings


def _bootstrap(client: TestClient, settings):
    response = client.post(
        "/api/auth/register",
        headers={"Authorization": f"Bearer {settings.api_access_token}"},
        json={
            "email": "admin@example.com",
            "full_name": "Primary Admin",
            "password": "strong-production-password-1",
            "role": "admin",
            "organization_name": "Admin Lifecycle",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["user"], {"Authorization": f"Bearer {payload['access_token']}"}


def test_admin_invitation_is_one_time_scoped_and_audited(tmp_path, monkeypatch) -> None:
    client, settings = _production_client(tmp_path, monkeypatch)
    admin, headers = _bootstrap(client, settings)
    project = client.post("/api/admin/projects", headers=headers, json={"name": "Restricted Plant"})
    assert project.status_code == 200
    project_id = project.json()["project_id"]

    invited = client.post(
        "/api/admin/invitations",
        headers=headers,
        json={
            "email": "engineer@example.com",
            "full_name": "Safety Engineer",
            "role": "safety",
            "project_ids": [project_id],
        },
    )
    assert invited.status_code == 200
    assert invited.headers["cache-control"] == "no-store"
    token = invited.json()["invitation_token"]
    invitation_id = invited.json()["invitation"]["invitation_id"]
    assert token not in str(client.get("/api/admin/invitations", headers=headers).json())

    with sqlite3.connect(settings.database_path) as connection:
        stored = connection.execute(
            "SELECT token_hash FROM admin_invitations WHERE invitation_id = ?", (invitation_id,)
        ).fetchone()[0]
    assert stored == hashlib.sha256(token.encode()).hexdigest()
    assert token != stored

    accepted = client.post(
        "/api/auth/invitations/accept",
        json={"invitation_token": token, "password": "strong-production-password-2"},
    )
    assert accepted.status_code == 200
    user = accepted.json()["user"]
    assert user["organization_id"] == admin["organization_id"]
    assert user["role"] == "safety"
    user_headers = {
        "Authorization": f"Bearer {accepted.json()['access_token']}",
        "X-Project-ID": project_id,
    }
    assert client.get("/api/documents", headers=user_headers).status_code == 200
    assert client.post(
        "/api/auth/invitations/accept",
        json={"invitation_token": token, "password": "strong-production-password-3"},
    ).status_code == 404

    audit = client.get("/api/admin/audit", headers=headers)
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()["events"]}
    assert {"organization.bootstrap", "project.created", "invitation.created", "invitation.accepted"} <= actions
    assert verify_database(settings.database_path)["admin_audit_events"] >= 4


def test_non_admin_cannot_manage_users_or_escalate_role(tmp_path, monkeypatch) -> None:
    client, settings = _production_client(tmp_path, monkeypatch)
    admin, headers = _bootstrap(client, settings)
    invitation = client.post(
        "/api/admin/invitations",
        headers=headers,
        json={"email": "operator@example.com", "full_name": "Operator User", "role": "operator"},
    ).json()
    accepted = client.post(
        "/api/auth/invitations/accept",
        json={
            "invitation_token": invitation["invitation_token"],
            "password": "strong-production-password-2",
        },
    ).json()
    operator_headers = {"Authorization": f"Bearer {accepted['access_token']}"}

    assert client.patch(
        f"/api/admin/users/{accepted['user']['user_id']}",
        headers=operator_headers,
        json={"role": "admin"},
    ).status_code == 403
    assert client.get("/api/admin/audit", headers=operator_headers).status_code == 403
    assert client.patch(
        f"/api/admin/users/{admin['user_id']}",
        headers=headers,
        json={"role": "operator"},
    ).status_code == 409


def test_admin_cross_tenant_resources_are_non_enumerable(tmp_path, monkeypatch) -> None:
    client, settings = _production_client(tmp_path, monkeypatch)
    admin_a, headers_a = _bootstrap(client, settings)
    organization_b = create_organization("Tenant B", database_path=settings.database_path)
    admin_b = create_user(
        "admin-b@example.com",
        "Tenant B Admin",
        "strong-production-password-b",
        role="admin",
        organization_id=organization_b,
        database_path=settings.database_path,
    )
    token_b = create_session(admin_b.user_id, database_path=settings.database_path)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    project_b = client.post("/api/admin/projects", headers=headers_b, json={"name": "Tenant B Project"}).json()
    invitation_b = client.post(
        "/api/admin/invitations",
        headers=headers_b,
        json={"email": "tenant-b-user@example.com", "full_name": "Tenant B User"},
    ).json()

    assert client.delete(
        f"/api/admin/invitations/{invitation_b['invitation']['invitation_id']}", headers=headers_a
    ).status_code == 404
    assert client.put(
        f"/api/admin/projects/{project_b['project_id']}/members/{admin_a['user_id']}", headers=headers_a
    ).status_code == 404
    assert client.get(
        f"/api/admin/projects/{project_b['project_id']}/members", headers=headers_a
    ).status_code == 404
    assert client.patch(
        f"/api/admin/users/{admin_b.user_id}", headers=headers_a, json={"role": "operator"}
    ).status_code == 404
    users_a = client.get("/api/admin/users", headers=headers_a).json()["users"]
    assert {user["organization_id"] for user in users_a} == {admin_a["organization_id"]}


def test_admin_membership_revocation_and_last_admin_guards(tmp_path, monkeypatch) -> None:
    client, settings = _production_client(tmp_path, monkeypatch)
    admin, headers = _bootstrap(client, settings)
    project = client.post("/api/admin/projects", headers=headers, json={"name": "Membership"}).json()
    invitation = client.post(
        "/api/admin/invitations",
        headers=headers,
        json={"email": "member@example.com", "full_name": "Project Member", "project_ids": [project["project_id"]]},
    ).json()
    accepted = client.post(
        "/api/auth/invitations/accept",
        json={"invitation_token": invitation["invitation_token"], "password": "strong-production-password-2"},
    ).json()
    user_id = accepted["user"]["user_id"]
    user_headers = {
        "Authorization": f"Bearer {accepted['access_token']}",
        "X-Project-ID": project["project_id"],
    }
    assert client.get("/api/documents", headers=user_headers).status_code == 200
    assert client.delete(
        f"/api/admin/projects/{project['project_id']}/members/{user_id}", headers=headers
    ).status_code == 200
    assert client.get("/api/documents", headers=user_headers).status_code == 404
    assert client.get(
        f"/api/admin/projects/{project['project_id']}/members", headers=headers
    ).json()["users"] == [admin]
    assert client.put(
        f"/api/admin/projects/{project['project_id']}/members/{user_id}", headers=headers
    ).status_code == 200
    assert client.get("/api/documents", headers=user_headers).status_code == 200
    assert client.delete(
        f"/api/admin/projects/{admin['organization_id']}/members/{user_id}", headers=headers
    ).status_code == 409
    assert client.patch(
        f"/api/admin/users/{admin['user_id']}", headers=headers, json={"is_active": False}
    ).status_code == 409


def test_admin_role_change_revokes_existing_sessions(tmp_path, monkeypatch) -> None:
    client, settings = _production_client(tmp_path, monkeypatch)
    _, headers = _bootstrap(client, settings)
    invitation = client.post(
        "/api/admin/invitations",
        headers=headers,
        json={"email": "reviewer@example.com", "full_name": "Reviewer User", "role": "safety"},
    ).json()
    accepted = client.post(
        "/api/auth/invitations/accept",
        json={"invitation_token": invitation["invitation_token"], "password": "strong-production-password-2"},
    ).json()
    user_id = accepted["user"]["user_id"]
    old_headers = {"Authorization": f"Bearer {accepted['access_token']}"}

    changed = client.patch(
        f"/api/admin/users/{user_id}", headers=headers, json={"role": "operator"}
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "operator"
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    login = client.post(
        "/api/auth/login",
        json={"email": "reviewer@example.com", "password": "strong-production-password-2"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "operator"


def test_revoked_expired_and_concurrently_accepted_invitations_fail_closed(tmp_path) -> None:
    database_path = tmp_path / "store.sqlite3"
    organization_id = create_organization("Invitation Store", database_path=database_path)
    admin = create_user(
        "store-admin@example.com",
        "Store Admin",
        "strong-password-1",
        role="admin",
        organization_id=organization_id,
        database_path=database_path,
    )
    invitation, token = create_invitation(
        organization_id,
        admin.user_id,
        "race@example.com",
        "Race User",
        "operator",
        [],
        ttl_seconds=300,
        database_path=database_path,
    )
    assert invitation.email == "race@example.com"

    def accept_once(_: int):
        try:
            return accept_invitation(token, "strong-password-race", database_path=database_path).user_id
        except (AdminConflict, AdminResourceNotFound):
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(accept_once, range(2)))
    assert len([result for result in results if result is not None]) == 1

    expired, expired_token = create_invitation(
        organization_id,
        admin.user_id,
        "expired@example.com",
        "Expired User",
        "operator",
        [],
        ttl_seconds=300,
        database_path=database_path,
    )
    with connect_database(database_path) as connection:
        connection.execute(
            "UPDATE admin_invitations SET expires_at = ? WHERE invitation_id = ?",
            (datetime(2020, 1, 1, tzinfo=UTC).isoformat(), expired.invitation_id),
        )
    with pytest.raises(AdminResourceNotFound):
        accept_invitation(expired_token, "strong-password-expired", database_path=database_path)


def test_admin_audit_events_are_append_only(tmp_path) -> None:
    database_path = tmp_path / "audit.sqlite3"
    organization_id = create_organization("Audit Admin", database_path=database_path)
    admin = create_user(
        "audit-admin@example.com",
        "Audit Admin",
        "strong-password-1",
        role="admin",
        organization_id=organization_id,
        database_path=database_path,
    )
    create_invitation(
        organization_id,
        admin.user_id,
        "audit-user@example.com",
        "Audit User",
        "operator",
        [],
        ttl_seconds=300,
        database_path=database_path,
    )
    with connect_database(database_path) as connection:
        event_id = connection.execute("SELECT event_id FROM admin_audit_events LIMIT 1").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("UPDATE admin_audit_events SET action = 'tampered' WHERE event_id = ?", (event_id,))
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM admin_audit_events WHERE event_id = ?", (event_id,))


def test_database_verification_rejects_cross_tenant_invitation_project(tmp_path) -> None:
    database_path = tmp_path / "tampered-invitation.sqlite3"
    organization_a = create_organization("Invite A", database_path=database_path)
    organization_b = create_organization("Invite B", database_path=database_path)
    admin_a = create_user(
        "invite-a-admin@example.com",
        "Invite A Admin",
        "strong-password-1",
        role="admin",
        organization_id=organization_a,
        database_path=database_path,
    )
    invitation, _ = create_invitation(
        organization_a,
        admin_a.user_id,
        "tampered@example.com",
        "Tampered User",
        "operator",
        [],
        ttl_seconds=300,
        database_path=database_path,
    )
    with connect_database(database_path) as connection:
        connection.execute(
            "UPDATE admin_invitations SET project_ids_json = ? WHERE invitation_id = ?",
            (f'["{organization_b}"]', invitation.invitation_id),
        )
    with pytest.raises(ValueError, match="invitation project membership"):
        verify_database(database_path)
