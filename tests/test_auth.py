import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.core.browser_auth import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, SESSION_COOKIE_NAME
from app.core import rate_limit
from app.core.organization import organization_storage_path
from app.main import app
from app.storage import auth_store
from app.storage.auth_store import (
    authenticate_user,
    create_bootstrap_user,
    create_session,
    cleanup_expired_sessions,
    create_browser_session,
    create_user,
    database_is_ready,
    get_user_by_token,
    list_users,
    revoke_session,
    revoke_user_sessions,
    session_csrf_is_valid,
)


def test_auth_store_creates_user_hashes_password_and_authenticates(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"

    user = create_user(
        email="MASTER@example.com",
        full_name="Мастер смены",
        password="strong-password-1",
        role="master",
        database_path=database_path,
    )
    authenticated = authenticate_user("master@example.com", "strong-password-1", database_path=database_path)
    rejected = authenticate_user("master@example.com", "wrong-password", database_path=database_path)
    token = create_session(user.user_id, database_path=database_path)
    token_user = get_user_by_token(token, database_path=database_path)

    assert user.email == "master@example.com"
    assert authenticated is not None
    assert authenticated.user_id == user.user_id
    assert rejected is None
    assert token_user is not None
    assert token_user.role == "master"

    with sqlite3.connect(database_path) as connection:
        stored_hash = connection.execute("SELECT password_hash FROM users WHERE user_id = ?", (user.user_id,)).fetchone()[0]
    assert "strong-password-1" not in stored_hash
    assert stored_hash.startswith("pbkdf2_sha256$")


def test_auth_store_rejects_duplicate_email(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    create_user("operator@example.com", "Оператор", "strong-password-1", database_path=database_path)

    try:
        create_user("OPERATOR@example.com", "Другой оператор", "strong-password-2", database_path=database_path)
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Duplicate email was accepted")

    assert len(list_users(database_path=database_path)) == 1


def test_auth_store_rejects_user_for_unknown_organization(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"

    with pytest.raises(ValueError, match="Organization does not exist"):
        create_user(
            "orphan@example.com",
            "Orphan User",
            "strong-password-1",
            organization_id="missing-organization",
            database_path=database_path,
        )

    assert list_users(database_path=database_path) == []


def test_organization_storage_path_rejects_symlink_escape(tmp_path) -> None:
    root = tmp_path / "tenant-root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "tenant-a").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes"):
        organization_storage_path(root, "tenant-a")


def test_missing_user_still_runs_password_verification(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    calls = 0
    original_verify = auth_store._verify_password

    def tracking_verify(password: str, stored_hash: str) -> bool:
        nonlocal calls
        calls += 1
        return original_verify(password, stored_hash)

    monkeypatch.setattr(auth_store, "_verify_password", tracking_verify)

    assert authenticate_user("missing@example.com", "wrong-password", database_path=database_path) is None
    assert calls == 1


def test_auth_store_rejects_untrusted_password_hash_cost(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    user = create_user("cost@example.com", "Cost User", "strong-password-1", database_path=database_path)
    malicious_hash = "pbkdf2_sha256$999999999$MTIzNDU2Nzg5MDEyMzQ1Ng==$MTIzNDU2Nzg5MDEyMzQ1Ng=="
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (malicious_hash, user.user_id))

    assert authenticate_user("cost@example.com", "strong-password-1", database_path=database_path) is None


def test_auth_store_rejects_non_positive_session_ttl(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    user = create_user("ttl@example.com", "TTL User", "strong-password-1", database_path=database_path)

    try:
        create_session(user.user_id, database_path=database_path, ttl_seconds=-1)
    except ValueError as exc:
        assert "TTL" in str(exc)
    else:
        raise AssertionError("Non-positive session TTL was accepted")


def test_browser_session_stores_only_token_hashes(tmp_path) -> None:
    database_path = tmp_path / "browser-session.sqlite3"
    user = create_user("browser@example.com", "Browser User", "strong-password-1", database_path=database_path)

    session_token, csrf_token = create_browser_session(user.user_id, database_path=database_path)

    assert get_user_by_token(session_token, database_path=database_path) is not None
    assert session_csrf_is_valid(session_token, csrf_token, database_path=database_path) is True
    assert session_csrf_is_valid(session_token, "x" * 43, database_path=database_path) is False
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT token_hash, csrf_token_hash FROM auth_sessions WHERE user_id = ?",
            (user.user_id,),
        ).fetchone()
    assert row is not None
    assert session_token not in row
    assert csrf_token not in row
    assert row[0] == hashlib.sha256(session_token.encode()).hexdigest()
    assert row[1] == hashlib.sha256(csrf_token.encode()).hexdigest()


def test_auth_store_caps_active_sessions(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    settings = get_settings().model_copy(update={"database_path": database_path, "auth_max_active_sessions": 2})
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    user = create_user("cap@example.com", "Session Cap", "strong-password-1", database_path=database_path)

    first = create_session(user.user_id, database_path=database_path)
    second = create_session(user.user_id, database_path=database_path)
    third = create_session(user.user_id, database_path=database_path)

    assert get_user_by_token(first, database_path=database_path) is None
    assert get_user_by_token(second, database_path=database_path) is not None
    assert get_user_by_token(third, database_path=database_path) is not None


def test_bootstrap_user_creation_is_atomic_under_concurrency(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"

    def attempt(index: int) -> bool:
        try:
            create_bootstrap_user(
                f"admin-{index}@example.com",
                f"Admin {index}",
                "strong-production-password-1",
                "admin",
                "Concurrent Test Organization",
                database_path=database_path,
            )
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(attempt, range(4)))

    assert results.count(True) == 1
    assert len(list_users(database_path=database_path)) == 1


def test_active_session_cap_is_atomic_under_concurrency(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "auth.sqlite3"
    settings = get_settings().model_copy(update={"database_path": database_path, "auth_max_active_sessions": 5})
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    user = create_user("parallel@example.com", "Parallel User", "strong-password-1", database_path=database_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _: create_session(user.user_id, database_path=database_path), range(20)))

    with sqlite3.connect(database_path) as connection:
        active = connection.execute(
            "SELECT COUNT(*) FROM auth_sessions WHERE revoked_at IS NULL AND expires_at > ?",
            ("2000-01-01T00:00:00+00:00",),
        ).fetchone()[0]
    assert active == 5


def test_auth_store_rejects_expired_and_revoked_sessions(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    user = create_user("session@example.com", "Session User", "strong-password-1", database_path=database_path)
    expired_token = create_session(user.user_id, database_path=database_path)
    active_token = create_session(user.user_id, database_path=database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE auth_sessions SET expires_at = ? WHERE token_hash = ?",
            ("2000-01-01T00:00:00+00:00", hashlib.sha256(expired_token.encode()).hexdigest()),
        )

    assert get_user_by_token(expired_token, database_path=database_path) is None
    assert get_user_by_token(active_token, database_path=database_path) is not None
    assert revoke_session(active_token, database_path=database_path) is True
    assert get_user_by_token(active_token, database_path=database_path) is None


def test_auth_store_rejects_idle_sessions_and_cleans_old_rows(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "idle-sessions.sqlite3"
    settings = get_settings().model_copy(
        update={
            "database_path": database_path,
            "auth_session_idle_timeout_seconds": 300,
            "auth_session_retention_seconds": 3_600,
        }
    )
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    user = create_user("idle@example.com", "Idle User", "strong-password-1", database_path=database_path)
    idle_token = create_session(user.user_id, database_path=database_path)
    old_token = create_session(user.user_id, database_path=database_path)
    old_timestamp = datetime(2020, 1, 1, tzinfo=UTC).isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
            (old_timestamp, hashlib.sha256(idle_token.encode()).hexdigest()),
        )
        connection.execute(
            "UPDATE auth_sessions SET expires_at = ?, last_seen_at = ? WHERE token_hash = ?",
            (old_timestamp, old_timestamp, hashlib.sha256(old_token.encode()).hexdigest()),
        )

    assert get_user_by_token(idle_token, database_path=database_path) is None
    assert cleanup_expired_sessions(database_path=database_path) == 1
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0] == 1


def test_auth_store_revokes_all_user_sessions(tmp_path) -> None:
    database_path = tmp_path / "auth.sqlite3"
    user = create_user("all@example.com", "All Sessions", "strong-password-1", database_path=database_path)
    tokens = [create_session(user.user_id, database_path=database_path) for _ in range(2)]

    assert revoke_user_sessions(user.user_id, database_path=database_path) == 2
    assert all(get_user_by_token(token, database_path=database_path) is None for token in tokens)


def test_auth_store_migrates_legacy_sessions_with_expiry(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    settings = get_settings().model_copy(update={"database_path": database_path})
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE users (user_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL, "
            "role TEXT NOT NULL, password_hash TEXT NOT NULL, is_active INTEGER NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE auth_sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
            "created_at TEXT NOT NULL, revoked_at TEXT)"
        )

    assert database_is_ready(database_path) is True
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(auth_sessions)").fetchall()}
    assert "expires_at" in columns
    assert "csrf_token_hash" in columns

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO users (user_id, email, full_name, role, password_hash, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("u1", "legacy@example.com", "Legacy", "operator", "invalid", 1, "2026-01-01T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, created_at, expires_at, revoked_at) "
            "VALUES (?, ?, ?, NULL, NULL)",
            ("legacy-token", "u1", "2026-01-01T00:00:00+00:00"),
        )
    assert database_is_ready(database_path) is False
    with sqlite3.connect(database_path) as connection:
        expires_at = connection.execute(
            "SELECT expires_at FROM auth_sessions WHERE token_hash = 'legacy-token'"
        ).fetchone()[0]
    assert expires_at is None


def test_auth_api_register_login_me_and_session_bearer_access(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={
            "api_access_token": "static-token",
            "database_path": tmp_path / "auth.sqlite3",
        }
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    client = TestClient(app)

    registered = client.post(
        "/api/auth/register",
        json={
            "email": "safety@example.com",
            "full_name": "Инженер ОТ",
            "password": "strong-password-1",
            "role": "safety",
        },
    )

    assert registered.status_code == 200
    token = registered.json()["access_token"]
    assert registered.json()["user"]["role"] == "safety"
    assert registered.json()["user"]["email"] == "safety@example.com"

    duplicate = client.post(
        "/api/auth/register",
        json={
            "email": "SAFETY@example.com",
            "full_name": "Инженер ОТ",
            "password": "strong-password-1",
            "role": "safety",
        },
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/api/auth/login",
        json={"email": "safety@example.com", "password": "strong-password-1"},
    )
    assert login.status_code == 200
    login_token = login.json()["access_token"]
    assert login_token != token

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login_token}"})
    assert me.status_code == 200
    assert me.json()["user"]["full_name"] == "Инженер ОТ"

    generated = client.post(
        "/api/instructions/generate",
        headers={"Authorization": f"Bearer {login_token}"},
        json={"task": "Проверить рабочее место перед запуском оборудования"},
    )
    assert generated.status_code == 200


def test_auth_config_hides_unsupported_production_registration_controls(monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={
            "api_access_token": "production-capability-token-at-least-32-characters",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
        }
    )
    monkeypatch.setattr("app.api.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)

    response = TestClient(app).get("/api/auth/config")

    assert response.status_code == 200
    assert response.json() == {
        "public_registration_enabled": False,
        "role_self_assignment_enabled": False,
        "allowed_registration_roles": ["operator"],
        "minimum_password_length": 12,
    }


def test_browser_cookie_login_hides_token_and_sets_hardened_production_cookies(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "browser-login.sqlite3"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "production-bootstrap-token-at-least-32-chars",
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": database_path,
        }
    )
    create_user(
        "cookie@example.com",
        "Cookie User",
        "strong-production-password-1",
        database_path=database_path,
    )
    monkeypatch.setattr("app.api.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.instructions.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    client = TestClient(app, base_url="https://testserver")

    login = client.post(
        "/api/auth/login",
        headers={"X-Auth-Transport": "cookie"},
        json={"email": "cookie@example.com", "password": "strong-production-password-1"},
    )

    assert login.status_code == 200
    assert login.json()["token_type"] == "cookie"
    assert "access_token" not in login.json()
    set_cookies = login.headers.get_list("set-cookie")
    session_cookie = next(item for item in set_cookies if item.startswith(f"{SESSION_COOKIE_NAME}="))
    csrf_cookie = next(item for item in set_cookies if item.startswith(f"{CSRF_COOKIE_NAME}="))
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=strict" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie
    assert "SameSite=strict" in csrf_cookie
    assert client.get("/api/auth/me").status_code == 200
    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    generated = client.post(
        "/api/instructions/generate",
        headers={CSRF_HEADER_NAME: csrf_token},
        json={"task": "Проверить рабочее место перед запуском оборудования"},
    )
    assert generated.status_code == 200


def test_cookie_authenticated_changes_require_server_validated_csrf(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "csrf.sqlite3"
    settings = get_settings().model_copy(update={"database_path": database_path})
    create_user("csrf@example.com", "CSRF User", "strong-password-1", database_path=database_path)
    monkeypatch.setattr("app.api.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        headers={"X-Auth-Transport": "cookie"},
        json={"email": "csrf@example.com", "password": "strong-password-1"},
    )
    assert login.status_code == 200
    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token

    missing = client.post("/api/auth/logout")
    wrong = client.post("/api/auth/logout", headers={CSRF_HEADER_NAME: "x" * 43})
    allowed = client.post("/api/auth/logout", headers={CSRF_HEADER_NAME: csrf_token})

    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_failed"
    assert wrong.status_code == 403
    assert wrong.json()["error"]["code"] == "csrf_failed"
    assert allowed.status_code == 200
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    assert client.cookies.get(CSRF_COOKIE_NAME) is None
    assert client.get("/api/auth/me").status_code == 401


def test_cookie_csrf_double_submit_value_must_match_server_hash(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "forged-csrf.sqlite3"
    settings = get_settings().model_copy(update={"database_path": database_path})
    create_user("forged@example.com", "Forged User", "strong-password-1", database_path=database_path)
    monkeypatch.setattr("app.api.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    client.post(
        "/api/auth/login",
        headers={"X-Auth-Transport": "cookie"},
        json={"email": "forged@example.com", "password": "strong-password-1"},
    )
    forged = "x" * 43
    client.cookies.set(CSRF_COOKIE_NAME, forged)

    response = client.post("/api/auth/logout", headers={CSRF_HEADER_NAME: forged})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_bearer_session_clients_do_not_require_csrf(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "bearer-no-csrf.sqlite3"
    settings = get_settings().model_copy(update={"database_path": database_path})
    user = create_user("bearer@example.com", "Bearer User", "strong-password-1", database_path=database_path)
    token = create_session(user.user_id, database_path=database_path)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)

    response = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_invalid_production_session_cookie_is_cleared_on_unauthorized_response(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": "production-bootstrap-token-at-least-32-chars",
            "allow_unauthenticated_access": False,
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": tmp_path / "expired-cookie.sqlite3",
        }
    )
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE_NAME, "expired-session-token")
    client.cookies.set(CSRF_COOKIE_NAME, "expired-csrf-token")

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    cleared = response.headers.get_list("set-cookie")
    assert any(item.startswith(f'{SESSION_COOKIE_NAME}=""') and "Max-Age=0" in item for item in cleared)
    assert any(item.startswith(f'{CSRF_COOKIE_NAME}=""') and "Max-Age=0" in item for item in cleared)


def test_auth_api_rejects_invalid_login(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(update={"database_path": tmp_path / "auth.sqlite3"})
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_registration_rejects_whitespace_only_identity_fields() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={
            "email": "blank-name@example.com",
            "full_name": "   ",
            "password": "strong-password-1",
            "organization_name": "   ",
        },
    )
    assert response.status_code == 422


def test_production_registration_requires_static_token_and_blocks_role_self_assignment(tmp_path, monkeypatch) -> None:
    bootstrap_token = "bootstrap-token-with-at-least-32-characters"
    settings = get_settings().model_copy(
        update={
            "deployment_mode": "production",
            "api_access_token": bootstrap_token,
            "auth_public_registration_enabled": False,
            "auth_allow_role_self_assignment": False,
            "auth_min_password_length": 12,
            "database_path": tmp_path / "auth.sqlite3",
        }
    )
    monkeypatch.setattr("app.api.auth.get_settings", lambda: settings)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    payload = {
        "email": "admin@example.com",
        "full_name": "Trusted Admin",
        "password": "strong-production-password-1",
        "role": "admin",
    }

    denied = client.post("/api/auth/register", json=payload)
    allowed = client.post(
        "/api/auth/register",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
        json=payload,
    )

    repeated_bootstrap = client.post(
        "/api/auth/register",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
        json={**payload, "email": "second-admin@example.com"},
    )
    admin_headers = {"Authorization": f"Bearer {allowed.json()['access_token']}"}
    admin_created_user = client.post(
        "/api/auth/register",
        headers=admin_headers,
        json={
            "email": "safety-provisioned@example.com",
            "full_name": "Provisioned Safety",
            "password": "strong-production-password-2",
            "role": "safety",
        },
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["user"]["role"] == "admin"
    assert allowed.json()["user"]["organization_id"] != "legacy"
    assert repeated_bootstrap.status_code == 403
    assert admin_created_user.status_code == 403


def test_auth_api_logout_revokes_server_session(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(update={"database_path": tmp_path / "auth.sqlite3"})
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    auth = client.post(
        "/api/auth/register",
        json={
            "email": "logout@example.com",
            "full_name": "Logout User",
            "password": "strong-password-1",
            "role": "operator",
        },
    ).json()
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    logged_out = client.post("/api/auth/logout", headers=headers)
    me_after_logout = client.get("/api/auth/me", headers=headers)

    assert logged_out.status_code == 200
    assert me_after_logout.status_code == 401


def test_auth_api_logout_all_revokes_every_user_session(tmp_path, monkeypatch) -> None:
    settings = get_settings().model_copy(update={"database_path": tmp_path / "auth.sqlite3"})
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)
    registered = client.post(
        "/api/auth/register",
        json={
            "email": "logout-all@example.com",
            "full_name": "Logout All User",
            "password": "strong-password-1",
            "role": "operator",
        },
    ).json()
    logged_in = client.post(
        "/api/auth/login",
        json={"email": "logout-all@example.com", "password": "strong-password-1"},
    ).json()
    first_headers = {"Authorization": f"Bearer {registered['access_token']}"}
    second_headers = {"Authorization": f"Bearer {logged_in['access_token']}"}

    response = client.post("/api/auth/logout-all", headers=second_headers)

    assert response.status_code == 200
    assert client.get("/api/auth/me", headers=first_headers).status_code == 401
    assert client.get("/api/auth/me", headers=second_headers).status_code == 401


def test_auth_login_endpoint_has_dedicated_rate_limit(tmp_path, monkeypatch) -> None:
    rate_limit.reset_rate_limit_state()
    settings = get_settings().model_copy(
        update={
            "database_path": tmp_path / "auth.sqlite3",
            "rate_limit_enabled": True,
            "auth_rate_limit_requests": 1,
            "auth_rate_limit_window_seconds": 300,
        }
    )
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: settings)
    monkeypatch.setattr("app.storage.auth_store.get_settings", lambda: settings)
    client = TestClient(app)

    first = client.post("/api/auth/login", json={"email": "missing@example.com", "password": "wrong-password"})
    second = client.post("/api/auth/login", json={"email": "missing@example.com", "password": "wrong-password"})

    assert first.status_code == 401
    assert second.status_code == 429
    rate_limit.reset_rate_limit_state()
