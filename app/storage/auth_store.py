from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from app.core.settings import Settings, get_settings
from app.core.organization import LEGACY_ORGANIZATION_ID
from app.core.authorization import default_project_id
from app.schemas.auth import UserPublic, UserRole
from app.storage.database import (
    apply_migrations,
    connect_database,
    database_is_available,
    database_is_healthy,
    database_is_read_only_ready,
)


PASSWORD_ITERATIONS = 210_000
MIN_STORED_PASSWORD_ITERATIONS = 100_000
MAX_STORED_PASSWORD_ITERATIONS = 1_000_000
LEGACY_ORGANIZATION_NAME = "Legacy Demo Organization"


def create_user(
    email: str,
    full_name: str,
    password: str,
    role: UserRole = "operator",
    organization_id: str = LEGACY_ORGANIZATION_ID,
    database_path: Path | None = None,
) -> UserPublic:
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        _begin_immediate(connection)
        try:
            user = insert_user_record(connection, email, full_name, password, role, organization_id)
        except sqlite3.IntegrityError as exc:
            raise ValueError("User with this email already exists") from exc
    return user


def create_bootstrap_user(
    email: str,
    full_name: str,
    password: str,
    role: UserRole,
    organization_name: str,
    database_path: Path | None = None,
) -> UserPublic:
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        _begin_immediate(connection)
        if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
            raise ValueError("Bootstrap registration is already complete")
        organization_id = _create_organization(connection, organization_name)
        user = insert_user_record(connection, email, full_name, password, role, organization_id)
        from app.storage.admin_store import append_admin_audit_event

        append_admin_audit_event(
            connection,
            organization_id=organization_id,
            actor_user_id=user.user_id,
            action="organization.bootstrap",
            target_type="organization",
            target_id=organization_id,
            details={"initial_admin_user_id": user.user_id},
        )
    return user


def create_organization(name: str, database_path: Path | None = None) -> str:
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        _begin_immediate(connection)
        return _create_organization(connection, name)


def authenticate_user(email: str, password: str, database_path: Path | None = None) -> UserPublic | None:
    settings = get_settings()
    now = datetime.now(UTC)
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (_normalize_email(email),),
        ).fetchone()

    # Verification always runs, for a missing account, a wrong password and a
    # locked account alike. Skipping it for any of those would make the three
    # distinguishable by response time, which is how account enumeration works.
    stored_hash = DUMMY_PASSWORD_HASH if row is None else str(row["password_hash"])
    password_matches = _verify_password(password, stored_hash)
    locked = row is not None and _lockout_is_active(row, now)

    if row is None:
        return None
    if not password_matches:
        _register_failed_login(row, now, settings, database_path)
        return None
    if locked:
        # The password was right, but the account is serving a lockout. Saying so
        # would confirm the password to whoever triggered the lockout.
        return None
    _clear_failed_logins(row, database_path)
    return _user_from_row(row)


def _lockout_is_active(row: sqlite3.Row, now: datetime) -> bool:
    recorded = str(row["locked_until"] or "")
    if not recorded:
        return False
    try:
        locked_until = datetime.fromisoformat(recorded)
    except ValueError:
        return False
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    return locked_until > now


def _register_failed_login(
    row: sqlite3.Row,
    now: datetime,
    settings: Settings,
    database_path: Path | None,
) -> None:
    attempts = int(row["failed_login_attempts"] or 0) + 1
    locked_until: str | None = None
    if attempts >= settings.auth_max_failed_attempts:
        locked_until = (now + timedelta(seconds=settings.auth_lockout_seconds)).isoformat()
        attempts = 0
    with _connect(database_path) as connection:
        connection.execute(
            "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE user_id = ?",
            (attempts, locked_until, str(row["user_id"])),
        )
        connection.commit()


def _clear_failed_logins(row: sqlite3.Row, database_path: Path | None) -> None:
    # Guarded so an ordinary sign-in does not write. Most sign-ins succeed with
    # the counter already at zero, and SQLite allows one writer.
    if not int(row["failed_login_attempts"] or 0) and not str(row["locked_until"] or ""):
        return
    with _connect(database_path) as connection:
        connection.execute(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE user_id = ?",
            (str(row["user_id"]),),
        )
        connection.commit()


def create_session(
    user_id: str,
    database_path: Path | None = None,
    ttl_seconds: int | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    _insert_session(user_id, token, None, database_path=database_path, ttl_seconds=ttl_seconds)
    return token


def create_browser_session(
    user_id: str,
    database_path: Path | None = None,
    ttl_seconds: int | None = None,
) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    _insert_session(
        user_id,
        token,
        _hash_token(csrf_token),
        database_path=database_path,
        ttl_seconds=ttl_seconds,
    )
    return token, csrf_token


def _insert_session(
    user_id: str,
    token: str,
    csrf_token_hash: str | None,
    *,
    database_path: Path | None,
    ttl_seconds: int | None,
) -> None:
    token_hash = _hash_token(token)
    now = datetime.now(UTC)
    settings = get_settings()
    ttl_seconds = settings.auth_session_ttl_seconds if ttl_seconds is None else ttl_seconds
    if ttl_seconds <= 0:
        raise ValueError("Session TTL must be positive")
    expires_at = now + timedelta(seconds=ttl_seconds)
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        _begin_immediate(connection)
        _cleanup_expired_sessions(connection, now, settings.auth_session_retention_seconds)
        idle_cutoff = now - timedelta(seconds=settings.auth_session_idle_timeout_seconds)
        active_sessions = connection.execute(
            """
            SELECT token_hash
            FROM auth_sessions
            WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ? AND last_seen_at > ?
            ORDER BY created_at DESC
            """,
            (user_id, now.isoformat(), idle_cutoff.isoformat()),
        ).fetchall()
        sessions_to_revoke = active_sessions[max(0, settings.auth_max_active_sessions - 1) :]
        for row in sessions_to_revoke:
            connection.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ?",
                (now.isoformat(), str(row["token_hash"])),
            )
        connection.execute(
            """
            INSERT INTO auth_sessions (
                token_hash, user_id, created_at, expires_at, revoked_at, csrf_token_hash, last_seen_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                token_hash,
                user_id,
                now.isoformat(),
                expires_at.isoformat(),
                csrf_token_hash,
                now.isoformat(),
            ),
        )


def get_user_by_token(token: str, database_path: Path | None = None) -> UserPublic | None:
    if not token:
        return None
    settings = get_settings()
    now = datetime.now(UTC)
    idle_cutoff = now - timedelta(seconds=settings.auth_session_idle_timeout_seconds)
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            """
            SELECT users.*, auth_sessions.last_seen_at AS session_last_seen_at
            FROM auth_sessions
            JOIN users ON users.user_id = auth_sessions.user_id
            WHERE auth_sessions.token_hash = ?
              AND auth_sessions.revoked_at IS NULL
              AND auth_sessions.expires_at > ?
              AND auth_sessions.last_seen_at > ?
              AND users.is_active = 1
            """,
            (_hash_token(token), now.isoformat(), idle_cutoff.isoformat()),
        ).fetchone()
        if row is not None and _last_seen_is_stale(row, now, settings):
            # Refresh the idle timer only once it has actually aged. This used to
            # run on every authenticated request: a write transaction per request
            # for a field whose only consumer is the idle-timeout comparison.
            # The staleness test uses the value already returned above, so the
            # common request issues no write statement at all rather than an
            # UPDATE that matches nothing — an UPDATE still takes a write lock.
            connection.execute(
                "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
                (now.isoformat(), _hash_token(token)),
            )
    if row is None:
        return None
    return _user_from_row(row)


def session_csrf_is_valid(
    session_token: str,
    csrf_token: str,
    database_path: Path | None = None,
) -> bool:
    if not session_token or not csrf_token or not 32 <= len(csrf_token) <= 128:
        return False
    settings = get_settings()
    now = datetime.now(UTC)
    idle_cutoff = now - timedelta(seconds=settings.auth_session_idle_timeout_seconds)
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        row = connection.execute(
            """
            SELECT csrf_token_hash
            FROM auth_sessions
            WHERE token_hash = ?
              AND revoked_at IS NULL
              AND expires_at > ?
              AND last_seen_at > ?
            """,
            (_hash_token(session_token), now.isoformat(), idle_cutoff.isoformat()),
        ).fetchone()
    if row is None or row["csrf_token_hash"] is None:
        return False
    return hmac.compare_digest(str(row["csrf_token_hash"]), _hash_token(csrf_token))


def revoke_session(token: str, database_path: Path | None = None) -> bool:
    if not token:
        return False
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        _begin_immediate(connection)
        result = connection.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (datetime.now(UTC).isoformat(), _hash_token(token)),
        )
    return result.rowcount > 0


def revoke_user_sessions(user_id: str, database_path: Path | None = None) -> int:
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        _begin_immediate(connection)
        result = connection.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (datetime.now(UTC).isoformat(), user_id),
        )
    return result.rowcount


def cleanup_expired_sessions(database_path: Path | None = None) -> int:
    settings = get_settings()
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        _begin_immediate(connection)
        return _cleanup_expired_sessions(
            connection,
            datetime.now(UTC),
            settings.auth_session_retention_seconds,
        )


def _cleanup_expired_sessions(
    connection: sqlite3.Connection,
    now: datetime,
    retention_seconds: int,
) -> int:
    cutoff = now - timedelta(seconds=retention_seconds)
    result = connection.execute(
        """
        DELETE FROM auth_sessions
        WHERE expires_at <= ? OR (revoked_at IS NOT NULL AND revoked_at <= ?)
        """,
        (cutoff.isoformat(), cutoff.isoformat()),
    )
    return result.rowcount


def list_users(database_path: Path | None = None) -> list[UserPublic]:
    with _connect(database_path) as connection:
        _ensure_schema(connection)
        rows = connection.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return [_user_from_row(row) for row in rows]


def database_is_ready(database_path: Path | None = None) -> bool:
    return database_is_healthy(database_path or get_settings().database_path)


def database_is_read_only(database_path: Path | None = None) -> bool:
    return database_is_read_only_ready(database_path or get_settings().database_path)


def database_is_present(database_path: Path | None = None) -> bool:
    return database_is_available(database_path or get_settings().database_path)


def _connect(database_path: Path | None = None) -> sqlite3.Connection:
    path = database_path or get_settings().database_path
    return connect_database(path)


def _begin_immediate(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        connection.commit()
    connection.execute("BEGIN IMMEDIATE")


def _last_seen_is_stale(row: sqlite3.Row, now: datetime, settings: Settings) -> bool:
    recorded = str(row["session_last_seen_at"] or "")
    if not recorded:
        return True
    try:
        last_seen = datetime.fromisoformat(recorded)
    except ValueError:
        return True
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    return (now - last_seen).total_seconds() >= _last_seen_refresh_seconds(settings)


def _last_seen_refresh_seconds(settings: Settings) -> int:
    """How stale `last_seen_at` may get before it is written again.

    Kept well below the idle timeout so a session is never dropped for looking
    idle when it is not: at a tenth of the timeout the recorded value trails
    reality by at most 10% of the window that decides expiry.
    """
    return max(1, settings.auth_session_idle_timeout_seconds // 10)


def _ensure_schema(connection: sqlite3.Connection) -> None:
    apply_migrations(connection, session_ttl_seconds=get_settings().auth_session_ttl_seconds)


def _new_user(email: str, full_name: str, role: UserRole, organization_id: str) -> UserPublic:
    return UserPublic(
        user_id=secrets.token_hex(16),
        organization_id=organization_id,
        project_id=default_project_id(organization_id),
        email=_normalize_email(email),
        full_name=full_name.strip(),
        role=role,
        is_active=True,
        created_at=datetime.now(UTC),
    )


def insert_user_record(
    connection: sqlite3.Connection,
    email: str,
    full_name: str,
    password: str,
    role: UserRole,
    organization_id: str,
) -> UserPublic:
    user = _new_user(email, full_name, role, organization_id)
    _insert_user(connection, user, _hash_password(password))
    return user


def _insert_user(connection: sqlite3.Connection, user: UserPublic, password_hash: str) -> None:
    organization_exists = connection.execute(
        "SELECT 1 FROM organizations WHERE organization_id = ?",
        (user.organization_id,),
    ).fetchone()
    if organization_exists is None:
        raise ValueError("Organization does not exist")
    connection.execute(
        """
        INSERT INTO users (
            user_id, organization_id, email, full_name, role, password_hash, is_active, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.user_id,
            user.organization_id,
            str(user.email),
            user.full_name,
            user.role,
            password_hash,
            int(user.is_active),
            user.created_at.isoformat(),
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO project_members (organization_id, project_id, user_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user.organization_id, user.project_id, user.user_id, datetime.now(UTC).isoformat()),
    )


def _create_organization(connection: sqlite3.Connection, name: str) -> str:
    normalized_name = name.strip()
    if len(normalized_name) < 2:
        raise ValueError("Organization name is required")
    organization_id = secrets.token_hex(16)
    connection.execute(
        "INSERT INTO organizations (organization_id, name, created_at) VALUES (?, ?, ?)",
        (organization_id, normalized_name, datetime.now(UTC).isoformat()),
    )
    connection.execute(
        """
        INSERT INTO projects (project_id, organization_id, name, is_default, created_at)
        VALUES (?, ?, ?, 1, ?)
        """,
        (
            default_project_id(organization_id),
            organization_id,
            f"{normalized_name} Default Project",
            datetime.now(UTC).isoformat(),
        ),
    )
    return organization_id


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_text, digest_text = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        if not MIN_STORED_PASSWORD_ITERATIONS <= iterations <= MAX_STORED_PASSWORD_ITERATIONS:
            return False
        salt = base64.b64decode(salt_text.encode("ascii"), validate=True)
        expected_digest = base64.b64decode(digest_text.encode("ascii"), validate=True)
        if not 8 <= len(salt) <= 64 or not 16 <= len(expected_digest) <= 64:
            return False
    except (binascii.Error, ValueError, TypeError):
        return False
    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)


DUMMY_PASSWORD_HASH = _hash_password("industrial-instruction-ai-dummy-password")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _user_from_row(row: sqlite3.Row) -> UserPublic:
    return UserPublic(
        user_id=str(row["user_id"]),
        organization_id=str(row["organization_id"]),
        project_id=default_project_id(str(row["organization_id"])),
        email=str(row["email"]),
        full_name=str(row["full_name"]),
        role=cast(UserRole, str(row["role"])),
        is_active=bool(row["is_active"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )
