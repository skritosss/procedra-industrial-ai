from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Callable, Literal

from app.core.settings import get_settings


CURRENT_SCHEMA_VERSION = 10
LEGACY_ORGANIZATION_ID = "legacy"
LEGACY_ORGANIZATION_NAME = "Legacy Demo Organization"
Migration = tuple[int, str, Callable[[sqlite3.Connection, int], None]]


class ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback) -> Literal[False]:
        try:
            super().__exit__(exc_type, exc_value, traceback)
            return False
        finally:
            self.close()


def connect_database(database_path: Path | None = None) -> sqlite3.Connection:
    path = database_path or get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0, factory=ManagedConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA foreign_keys = ON")
    enable_wal(connection)
    return connection


_APPLIED_SCHEMA_VERSIONS: dict[str, int] = {}


def reset_schema_cache() -> None:
    """Forget which database files have had their schema verified.

    Needed whenever a database file is replaced underneath a running process —
    a restore, or a test that recreates a database at a path already seen.
    """
    _APPLIED_SCHEMA_VERSIONS.clear()


def _database_key(connection: sqlite3.Connection) -> str | None:
    """Identify the main database file, or None for in-memory databases."""
    try:
        for row in connection.execute("PRAGMA database_list"):
            if row[1] == "main":
                path = str(row[2] or "")
                return path or None
    except sqlite3.Error:
        return None
    return None


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    session_ttl_seconds: int = 86_400,
    force: bool = False,
) -> int:
    """Bring the schema up to date, at most once per database per process.

    This used to run on every storage operation, and it is not a read: it
    executes `CREATE TABLE IF NOT EXISTS` and commits before doing anything
    else. Since SQLite allows one writer, every authenticated request paid for a
    write transaction purely to re-confirm a schema that cannot change while the
    process runs.

    The schema is applied at startup and on the first use of any database file;
    afterwards the recorded version is returned without touching the connection.
    Pass `force=True` to re-run the check, and call `reset_schema_cache()` when a
    database file is replaced.
    """
    key = _database_key(connection)
    if not force and key is not None:
        cached = _APPLIED_SCHEMA_VERSIONS.get(key)
        if cached is not None:
            return cached
    version = _apply_migrations_now(connection, session_ttl_seconds=session_ttl_seconds)
    if key is not None:
        _APPLIED_SCHEMA_VERSIONS[key] = version
    return version


def _apply_migrations_now(connection: sqlite3.Connection, *, session_ttl_seconds: int = 86_400) -> int:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    installed_version = current_schema_version(connection)
    if installed_version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"Database schema version {installed_version} is newer than supported version {CURRENT_SCHEMA_VERSION}"
        )
    expected_names = {version: name for version, name, _ in MIGRATIONS}
    for row in connection.execute("SELECT version, name FROM schema_migrations").fetchall():
        version = int(row["version"])
        if version in expected_names and str(row["name"]) != expected_names[version]:
            raise ValueError(f"Database migration {version} has an unexpected name")
    for version, name, migration in MIGRATIONS:
        if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            continue
        try:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
                connection.commit()
                continue
            migration(connection, session_ttl_seconds)
            connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, datetime.now(UTC).isoformat()),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return current_schema_version(connection)


def current_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
    return int(row["version"] if row is not None else 0)


def database_is_healthy(database_path: Path | None = None) -> bool:
    try:
        with connect_database(database_path) as connection:
            apply_migrations(connection)
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                return False
            _verify_audit_event_chains(connection)
            _verify_admin_audit_event_chains(connection)
            _verify_authorization_integrity(connection)
            return True
    except (OSError, sqlite3.Error, ValueError):
        return False


def database_is_available(database_path: Path | None = None) -> bool:
    """Cheap liveness check for an already initialized database.

    Answers only "is the expected database there and at the schema this build
    understands". Deliberately does not run `PRAGMA integrity_check` and does not
    recompute the audit hash chains: those are proportional to the whole database
    and to the entire audit history, so an unauthenticated caller could make the
    service do unbounded work, and the cost grows the longer the system runs.

    The deep verification lives in `database_is_read_only_ready`, reached through
    the authenticated `/ready/details` and `scripts/manage_database.py verify`.
    """
    path = (database_path or get_settings().database_path).resolve()
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            return int(row["version"] if row is not None else 0) == CURRENT_SCHEMA_VERSION
    except (OSError, sqlite3.Error):
        return False


def database_is_read_only_ready(database_path: Path | None = None) -> bool:
    """Verify an already initialized database without creating or migrating it."""
    path = (database_path or get_settings().database_path).resolve()
    if not path.is_file():
        return False
    try:
        result = verify_database(path)
    except (OSError, ValueError):
        return False
    return result["schema_version"] == CURRENT_SCHEMA_VERSION


def backup_database(source_path: Path, backup_path: Path) -> Path:
    source = source_path.resolve()
    destination = backup_path.resolve()
    if source == destination:
        raise ValueError("Backup destination must differ from the source database")
    if not source.is_file():
        raise ValueError("Source database does not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.urandom(4).hex()}.tmp")
    try:
        with closing(sqlite3.connect(f"file:{source}?mode=ro", uri=True)) as source_connection:
            source_connection.execute("PRAGMA busy_timeout = 10000")
            with closing(sqlite3.connect(temporary)) as backup_connection:
                source_connection.backup(backup_connection)
        os.chmod(temporary, 0o600)
        verify_database(temporary)
        temporary.replace(destination)
        Path(f"{destination}-wal").unlink(missing_ok=True)
        Path(f"{destination}-shm").unlink(missing_ok=True)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def restore_database(backup_path: Path, target_path: Path, *, safety_backup_path: Path | None = None) -> Path:
    source = backup_path.resolve()
    target = target_path.resolve()
    if source == target:
        raise ValueError("Restore source must differ from the target database")
    source_verification = verify_database(source)
    if source_verification["schema_version"] != CURRENT_SCHEMA_VERSION:
        raise ValueError(
            "Restore source schema version does not match the application schema version"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if safety_backup_path is None:
            raise ValueError("A safety backup path is required when replacing an existing database")
        backup_database(target, safety_backup_path)
    temporary = target.with_name(f".{target.name}.{os.urandom(4).hex()}.restore.tmp")
    try:
        with closing(sqlite3.connect(source)) as source_connection:
            with closing(sqlite3.connect(temporary)) as target_connection:
                source_connection.backup(target_connection)
        os.chmod(temporary, 0o600)
        verify_database(temporary)
        temporary.replace(target)
        Path(f"{target}-wal").unlink(missing_ok=True)
        Path(f"{target}-shm").unlink(missing_ok=True)
        # The file behind this path is a different database now, so the recorded
        # schema version no longer describes it.
        reset_schema_cache()
        return target
    finally:
        temporary.unlink(missing_ok=True)


def verify_database(database_path: Path) -> dict[str, int | str]:
    path = database_path.resolve()
    if not path.is_file():
        raise ValueError("Database file does not exist")
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or str(integrity[0]).lower() != "ok":
                raise ValueError(f"Database integrity check failed: {integrity[0] if integrity else 'no result'}")
            migration_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
            ).fetchone()
            version = 0
            if migration_table:
                row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
                version = int(row[0]) if row else 0
            instruction_count = _table_count(connection, "instruction_versions")
            audit_count = _table_count(connection, "instruction_audit_events")
            execution_count = _table_count(connection, "instruction_execution_runs")
            project_count = _table_count(connection, "projects")
            resource_count = _table_count(connection, "resource_ownership")
            admin_audit_count = _table_count(connection, "admin_audit_events")
            rate_limit_event_count = _table_count(connection, "rate_limit_events")
            video_job_count = _table_count(connection, "video_jobs")
            _verify_audit_event_chains(connection)
            _verify_admin_audit_event_chains(connection)
            _verify_authorization_integrity(connection)
    except sqlite3.Error as exc:
        raise ValueError(f"Unable to verify database: {exc}") from exc
    return {
        "status": "ok",
        "schema_version": version,
        "instruction_versions": instruction_count,
        "audit_events": audit_count,
        "execution_runs": execution_count,
        "projects": project_count,
        "resource_ownership": resource_count,
        "admin_audit_events": admin_audit_count,
        "rate_limit_events": rate_limit_event_count,
        "video_jobs": video_job_count,
        "audit_chain": "ok",
        "admin_audit_chain": "ok",
        "authorization_integrity": "ok",
    }


def _table_count(connection: sqlite3.Connection, table: str) -> int:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if not exists:
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def audit_event_hash(
    organization_id: str,
    instruction_id: str,
    version: int,
    sequence: int,
    previous_event_hash: str,
    event_json: str,
) -> str:
    material = "\x1f".join(
        [organization_id, instruction_id, str(version), str(sequence), previous_event_hash, event_json]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def admin_audit_event_hash(
    organization_id: str,
    sequence: int,
    previous_event_hash: str,
    event_id: str,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str,
    details_json: str,
    created_at: str,
) -> str:
    material = "\x1f".join(
        [
            organization_id,
            str(sequence),
            previous_event_hash,
            event_id,
            actor_user_id,
            action,
            target_type,
            target_id,
            details_json,
            created_at,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _verify_audit_event_chains(connection: sqlite3.Connection) -> None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'instruction_audit_events'"
    ).fetchone()
    if not exists:
        return
    rows = connection.execute(
        """
        SELECT organization_id, instruction_id, version, sequence,
               previous_event_hash, event_hash, event_json
        FROM instruction_audit_events
        ORDER BY organization_id, instruction_id, version, sequence
        """
    ).fetchall()
    parents: dict[tuple[str, str, int], tuple[int, str]] = {}
    for row in rows:
        parent = (str(row[0]), str(row[1]), int(row[2]))
        sequence = int(row[3])
        previous = str(row[4])
        expected_sequence, expected_previous = parents.get(parent, (1, ""))
        if sequence != expected_sequence or previous != expected_previous:
            raise ValueError("Audit event chain sequence is invalid")
        computed = audit_event_hash(*parent, sequence, previous, str(row[6]))
        if not hmac.compare_digest(computed, str(row[5])):
            raise ValueError("Audit event chain hash is invalid")
        parents[parent] = (sequence + 1, computed)


def _verify_admin_audit_event_chains(connection: sqlite3.Connection) -> None:
    columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(admin_audit_events)").fetchall()
    }
    if not {"sequence", "previous_event_hash", "event_hash"} <= columns:
        return
    rows = connection.execute(
        """
        SELECT organization_id, sequence, previous_event_hash, event_hash,
               event_id, actor_user_id, action, target_type, target_id,
               details_json, created_at
        FROM admin_audit_events
        ORDER BY organization_id, sequence
        """
    ).fetchall()
    parents: dict[str, tuple[int, str]] = {}
    for row in rows:
        organization_id = str(row["organization_id"])
        sequence = int(row["sequence"])
        previous = str(row["previous_event_hash"])
        expected_sequence, expected_previous = parents.get(organization_id, (1, ""))
        if sequence != expected_sequence or previous != expected_previous:
            raise ValueError("Admin audit event chain sequence is invalid")
        computed = admin_audit_event_hash(
            organization_id,
            sequence,
            previous,
            str(row["event_id"]),
            str(row["actor_user_id"]),
            str(row["action"]),
            str(row["target_type"]),
            str(row["target_id"]),
            str(row["details_json"]),
            str(row["created_at"]),
        )
        if not hmac.compare_digest(computed, str(row["event_hash"])):
            raise ValueError("Admin audit event chain hash is invalid")
        parents[organization_id] = (sequence + 1, computed)


def _verify_authorization_integrity(connection: sqlite3.Connection) -> None:
    required_tables = {
        "organizations",
        "users",
        "projects",
        "project_members",
        "resource_ownership",
        "admin_invitations",
        "admin_audit_events",
    }
    present_tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if not required_tables <= present_tables:
        return
    if current_schema_version(connection) >= 7:
        _verify_composite_tenant_foreign_keys(connection)
    foreign_key_violation = connection.execute("PRAGMA foreign_key_check").fetchone()
    if foreign_key_violation is not None:
        raise ValueError("Database foreign-key integrity check failed")
    checks = [
        """
        SELECT 1 FROM projects p
        LEFT JOIN organizations o ON o.organization_id = p.organization_id
        WHERE o.organization_id IS NULL LIMIT 1
        """,
        """
        SELECT 1 FROM project_members pm
        LEFT JOIN projects p
          ON p.project_id = pm.project_id AND p.organization_id = pm.organization_id
        LEFT JOIN users u
          ON u.user_id = pm.user_id AND u.organization_id = pm.organization_id
        WHERE p.project_id IS NULL OR u.user_id IS NULL LIMIT 1
        """,
        """
        SELECT 1 FROM resource_ownership r
        LEFT JOIN projects p
          ON p.project_id = r.project_id AND p.organization_id = r.organization_id
        LEFT JOIN users u
          ON u.user_id = r.owner_user_id AND u.organization_id = r.organization_id
        WHERE p.project_id IS NULL
           OR (r.owner_user_id IS NOT NULL AND u.user_id IS NULL)
        LIMIT 1
        """,
        """
        SELECT 1 FROM organizations o
        LEFT JOIN projects p
          ON p.organization_id = o.organization_id
         AND p.project_id = o.organization_id
         AND p.is_default = 1
        WHERE p.project_id IS NULL LIMIT 1
        """,
        """
        SELECT 1 FROM users u
        LEFT JOIN project_members pm
          ON pm.organization_id = u.organization_id
         AND pm.project_id = u.organization_id
         AND pm.user_id = u.user_id
        WHERE pm.user_id IS NULL LIMIT 1
        """,
        """
        SELECT 1 FROM admin_invitations i
        LEFT JOIN organizations o ON o.organization_id = i.organization_id
        LEFT JOIN users u
          ON u.user_id = i.created_by_user_id AND u.organization_id = i.organization_id
        WHERE o.organization_id IS NULL OR u.user_id IS NULL LIMIT 1
        """,
        """
        SELECT 1 FROM admin_audit_events a
        LEFT JOIN organizations o ON o.organization_id = a.organization_id
        LEFT JOIN users u
          ON u.user_id = a.actor_user_id AND u.organization_id = a.organization_id
        WHERE o.organization_id IS NULL OR u.user_id IS NULL LIMIT 1
        """,
    ]
    if "instruction_versions" in present_tables:
        checks.extend(
            [
                """
                SELECT 1 FROM instruction_versions i
                LEFT JOIN projects p
                  ON p.project_id = i.project_id AND p.organization_id = i.organization_id
                WHERE i.project_id IS NULL OR p.project_id IS NULL LIMIT 1
                """,
                """
                SELECT 1 FROM instruction_versions i
                LEFT JOIN resource_ownership r
                  ON r.organization_id = i.organization_id
                 AND r.project_id = i.project_id
                 AND r.resource_type = 'instruction'
                 AND r.resource_id = i.instruction_id
                WHERE r.resource_id IS NULL LIMIT 1
                """,
                """
                SELECT 1 FROM resource_ownership r
                LEFT JOIN instruction_versions i
                  ON i.organization_id = r.organization_id
                 AND i.project_id = r.project_id
                 AND i.instruction_id = r.resource_id
                WHERE r.resource_type = 'instruction' AND i.instruction_id IS NULL
                LIMIT 1
                """,
            ]
        )
    for query in checks:
        if connection.execute(query).fetchone() is not None:
            raise ValueError("Authorization ownership integrity check failed")
    invitation_rows = connection.execute(
        "SELECT organization_id, project_ids_json FROM admin_invitations"
    ).fetchall()
    for row in invitation_rows:
        try:
            project_ids = json.loads(str(row["project_ids_json"]))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Admin invitation project membership is invalid") from exc
        if not isinstance(project_ids, list) or not all(isinstance(item, str) for item in project_ids):
            raise ValueError("Admin invitation project membership is invalid")
        for project_id in project_ids:
            project = connection.execute(
                "SELECT 1 FROM projects WHERE organization_id = ? AND project_id = ?",
                (str(row["organization_id"]), project_id),
            ).fetchone()
            if project is None:
                raise ValueError("Admin invitation project membership is invalid")
    for row in connection.execute("SELECT details_json FROM admin_audit_events").fetchall():
        try:
            details = json.loads(str(row["details_json"]))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Admin audit event details are invalid") from exc
        if not isinstance(details, dict):
            raise ValueError("Admin audit event details are invalid")


def enable_wal(connection: sqlite3.Connection) -> None:
    """Switch the database to WAL, waiting out a concurrent switch.

    The journal mode is a property of the file, so several processes starting at
    once all try to set it and all but one can be refused outright with
    "database is locked" — busy_timeout does not arbitrate this one. Whoever wins
    sets it permanently; the rest only have to wait for that to land.
    """
    for attempt in range(20):
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 19:
                raise
            sleep(0.05)


def _migration_auth_foundation(connection: sqlite3.Connection, session_ttl_seconds: int) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            organization_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO organizations (organization_id, name, created_at) VALUES (?, ?, ?)",
        (LEGACY_ORGANIZATION_ID, LEGACY_ORGANIZATION_NAME, datetime.now(UTC).isoformat()),
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL DEFAULT 'legacy',
            email TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('operator', 'master', 'technologist', 'safety', 'quality', 'admin')),
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )
    user_columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(users)").fetchall()}
    if "organization_id" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN organization_id TEXT NOT NULL DEFAULT 'legacy'")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            revoked_at TEXT
        )
        """
    )
    session_columns = {
        str(row["name"]) for row in connection.execute("PRAGMA table_info(auth_sessions)").fetchall()
    }
    if "expires_at" not in session_columns:
        connection.execute("ALTER TABLE auth_sessions ADD COLUMN expires_at TEXT")
        default_expiry = datetime.now(UTC).timestamp() + session_ttl_seconds
        expires_at = datetime.fromtimestamp(default_expiry, UTC).isoformat()
        connection.execute("UPDATE auth_sessions SET expires_at = ? WHERE expires_at IS NULL", (expires_at,))
    connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at)")


def _migration_instruction_lifecycle(connection: sqlite3.Connection, _: int) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS instruction_versions (
            organization_id TEXT NOT NULL,
            instruction_id TEXT NOT NULL,
            version INTEGER NOT NULL CHECK (version >= 1),
            record_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (organization_id, instruction_id, version)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS instruction_audit_events (
            event_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            instruction_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            sequence INTEGER NOT NULL CHECK (sequence >= 1),
            event_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            previous_event_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL UNIQUE,
            UNIQUE (organization_id, instruction_id, version, sequence),
            FOREIGN KEY (organization_id, instruction_id, version)
                REFERENCES instruction_versions (organization_id, instruction_id, version)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS instruction_execution_runs (
            run_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            instruction_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            record_json TEXT NOT NULL,
            detail_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (organization_id, instruction_id, version)
                REFERENCES instruction_versions (organization_id, instruction_id, version)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS legacy_history_imports (
            source_path TEXT PRIMARY KEY,
            source_sha256 TEXT NOT NULL,
            imported_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_instruction_versions_org_created "
        "ON instruction_versions (organization_id, created_at DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_instruction_audit_parent "
        "ON instruction_audit_events (organization_id, instruction_id, version, sequence)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_instruction_execution_org_created "
        "ON instruction_execution_runs (organization_id, created_at DESC)"
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS instruction_audit_events_no_update
        BEFORE UPDATE ON instruction_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'instruction audit events are append-only');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS instruction_audit_events_no_delete
        BEFORE DELETE ON instruction_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'instruction audit events are append-only');
        END
        """
    )


def _migration_project_ownership(connection: sqlite3.Connection, _: int) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            project_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            name TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE (organization_id, project_id)
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_one_default
        ON projects (organization_id)
        WHERE is_default = 1
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS project_members (
            organization_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (project_id, user_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_ownership (
            organization_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            resource_type TEXT NOT NULL CHECK (resource_type IN ('document', 'instruction', 'video')),
            resource_id TEXT NOT NULL,
            owner_user_id TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (organization_id, resource_type, resource_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE RESTRICT
        )
        """
    )
    now = datetime.now(UTC).isoformat()
    connection.execute(
        """
        INSERT OR IGNORE INTO projects (project_id, organization_id, name, is_default, created_at)
        SELECT organization_id, organization_id, name || ' Default Project', 1, ?
        FROM organizations
        """,
        (now,),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO project_members (organization_id, project_id, user_id, created_at)
        SELECT organization_id, organization_id, user_id, ?
        FROM users
        """,
        (now,),
    )
    version_columns = {
        str(row["name"]) for row in connection.execute("PRAGMA table_info(instruction_versions)").fetchall()
    }
    if "project_id" not in version_columns:
        connection.execute("ALTER TABLE instruction_versions ADD COLUMN project_id TEXT")
        connection.execute("UPDATE instruction_versions SET project_id = organization_id WHERE project_id IS NULL")
    if "owner_user_id" not in version_columns:
        connection.execute("ALTER TABLE instruction_versions ADD COLUMN owner_user_id TEXT")
    connection.execute(
        """
        INSERT OR IGNORE INTO resource_ownership (
            organization_id, project_id, resource_type, resource_id, owner_user_id, created_at
        )
        SELECT organization_id, project_id, 'instruction', instruction_id, owner_user_id, MIN(created_at)
        FROM instruction_versions
        GROUP BY organization_id, project_id, instruction_id
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_resource_ownership_project "
        "ON resource_ownership (organization_id, project_id, resource_type)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_instruction_versions_project "
        "ON instruction_versions (organization_id, project_id, created_at DESC)"
    )


def _migration_admin_lifecycle(connection: sqlite3.Connection, _: int) -> None:
    connection.execute(
        """
        CREATE TABLE admin_invitations (
            invitation_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('operator', 'master', 'technologist', 'safety', 'quality', 'admin')),
            project_ids_json TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_by_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            accepted_at TEXT,
            revoked_at TEXT,
            CHECK (accepted_at IS NULL OR revoked_at IS NULL)
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX idx_admin_invitations_pending_email
        ON admin_invitations (organization_id, email)
        WHERE accepted_at IS NULL AND revoked_at IS NULL
        """
    )
    connection.execute(
        "CREATE INDEX idx_admin_invitations_expiry ON admin_invitations (expires_at)"
    )
    connection.execute(
        """
        CREATE TABLE admin_audit_events (
            event_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
            actor_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_admin_audit_org_created "
        "ON admin_audit_events (organization_id, created_at DESC)"
    )
    connection.execute(
        """
        CREATE TRIGGER admin_audit_events_no_update
        BEFORE UPDATE ON admin_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'admin audit events are append-only');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER admin_audit_events_no_delete
        BEFORE DELETE ON admin_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'admin audit events are append-only');
        END
        """
    )


def _migration_shared_rate_limit(connection: sqlite3.Connection, _: int) -> None:
    connection.execute(
        """
        CREATE TABLE rate_limit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bucket_hash TEXT NOT NULL,
            occurred_at REAL NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_rate_limit_bucket_time ON rate_limit_events (bucket_hash, occurred_at)"
    )
    connection.execute(
        "CREATE INDEX idx_rate_limit_event_time ON rate_limit_events (occurred_at)"
    )


def _migration_admin_audit_hash_chain(connection: sqlite3.Connection, _: int) -> None:
    connection.execute("DROP TRIGGER IF EXISTS admin_audit_events_no_update")
    connection.execute("DROP TRIGGER IF EXISTS admin_audit_events_no_delete")
    columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(admin_audit_events)").fetchall()
    }
    if "sequence" not in columns:
        connection.execute("ALTER TABLE admin_audit_events ADD COLUMN sequence INTEGER")
    if "previous_event_hash" not in columns:
        connection.execute("ALTER TABLE admin_audit_events ADD COLUMN previous_event_hash TEXT")
    if "event_hash" not in columns:
        connection.execute("ALTER TABLE admin_audit_events ADD COLUMN event_hash TEXT")

    rows = connection.execute(
        """
        SELECT event_id, organization_id, actor_user_id, action,
               target_type, target_id, details_json, created_at
        FROM admin_audit_events
        ORDER BY organization_id, created_at, event_id
        """
    ).fetchall()
    chain_heads: dict[str, tuple[int, str]] = {}
    for row in rows:
        organization_id = str(row["organization_id"])
        sequence, previous = chain_heads.get(organization_id, (1, ""))
        event_hash = admin_audit_event_hash(
            organization_id,
            sequence,
            previous,
            str(row["event_id"]),
            str(row["actor_user_id"]),
            str(row["action"]),
            str(row["target_type"]),
            str(row["target_id"]),
            str(row["details_json"]),
            str(row["created_at"]),
        )
        connection.execute(
            """
            UPDATE admin_audit_events
            SET sequence = ?, previous_event_hash = ?, event_hash = ?
            WHERE event_id = ?
            """,
            (sequence, previous, event_hash, str(row["event_id"])),
        )
        chain_heads[organization_id] = (sequence + 1, event_hash)

    connection.execute(
        "CREATE UNIQUE INDEX idx_admin_audit_org_sequence "
        "ON admin_audit_events (organization_id, sequence)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX idx_admin_audit_event_hash ON admin_audit_events (event_hash)"
    )
    connection.execute(
        """
        CREATE TRIGGER admin_audit_events_no_update
        BEFORE UPDATE ON admin_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'admin audit events are append-only');
        END
        """
    )
    connection.execute(
        """
        CREATE TRIGGER admin_audit_events_no_delete
        BEFORE DELETE ON admin_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'admin audit events are append-only');
        END
        """
    )


def _migration_browser_session_csrf(connection: sqlite3.Connection, _: int) -> None:
    columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(auth_sessions)").fetchall()}
    if "csrf_token_hash" not in columns:
        connection.execute("ALTER TABLE auth_sessions ADD COLUMN csrf_token_hash TEXT")


def _migration_session_idle_tracking(connection: sqlite3.Connection, _: int) -> None:
    columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(auth_sessions)").fetchall()}
    if "last_seen_at" not in columns:
        connection.execute("ALTER TABLE auth_sessions ADD COLUMN last_seen_at TEXT")
    connection.execute("UPDATE auth_sessions SET last_seen_at = created_at WHERE last_seen_at IS NULL")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_last_seen ON auth_sessions(last_seen_at)")


def _migration_durable_video_jobs(connection: sqlite3.Connection, _: int) -> None:
    connection.execute(
        """
        CREATE TABLE video_jobs (
            job_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            owner_user_id TEXT,
            job_type TEXT NOT NULL CHECK (job_type = 'extract_keyframes'),
            source_kind TEXT NOT NULL CHECK (source_kind IN ('upload', 'url')),
            status TEXT NOT NULL CHECK (
                status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
            ),
            stage TEXT NOT NULL,
            progress_percent INTEGER NOT NULL DEFAULT 0 CHECK (
                progress_percent >= 0 AND progress_percent <= 100
            ),
            request_json TEXT NOT NULL,
            result_json TEXT,
            error_code TEXT,
            error_message TEXT,
            idempotency_key TEXT NOT NULL,
            video_id TEXT,
            artifact_path TEXT,
            attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
            available_at TEXT NOT NULL,
            lease_owner TEXT,
            lease_expires_at TEXT,
            heartbeat_at TEXT,
            cancel_requested_at TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE (organization_id, project_id, idempotency_key),
            FOREIGN KEY (organization_id, project_id)
                REFERENCES projects(organization_id, project_id) ON DELETE CASCADE,
            FOREIGN KEY (organization_id, owner_user_id)
                REFERENCES users(organization_id, user_id) ON DELETE RESTRICT
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_video_jobs_claim ON video_jobs(status, available_at, created_at)"
    )
    connection.execute(
        "CREATE INDEX idx_video_jobs_lease ON video_jobs(status, lease_expires_at)"
    )
    connection.execute(
        "CREATE INDEX idx_video_jobs_scope "
        "ON video_jobs(organization_id, project_id, created_at DESC)"
    )


def _migration_composite_tenant_foreign_keys(connection: sqlite3.Connection, _: int) -> None:
    _validate_composite_tenant_rows(connection)
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_organization_user "
        "ON users (organization_id, user_id)"
    )
    connection.execute(
        """
        CREATE TABLE project_members_v7 (
            organization_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (project_id, user_id),
            FOREIGN KEY (organization_id, project_id)
                REFERENCES projects(organization_id, project_id) ON DELETE CASCADE,
            FOREIGN KEY (organization_id, user_id)
                REFERENCES users(organization_id, user_id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        INSERT INTO project_members_v7 (organization_id, project_id, user_id, created_at)
        SELECT organization_id, project_id, user_id, created_at FROM project_members
        """
    )
    connection.execute(
        """
        CREATE TABLE resource_ownership_v7 (
            organization_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            resource_type TEXT NOT NULL CHECK (
                resource_type IN ('document', 'instruction', 'video')
            ),
            resource_id TEXT NOT NULL,
            owner_user_id TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (organization_id, resource_type, resource_id),
            FOREIGN KEY (organization_id, project_id)
                REFERENCES projects(organization_id, project_id) ON DELETE RESTRICT,
            FOREIGN KEY (organization_id, owner_user_id)
                REFERENCES users(organization_id, user_id) ON DELETE RESTRICT
        )
        """
    )
    connection.execute(
        """
        INSERT INTO resource_ownership_v7 (
            organization_id, project_id, resource_type, resource_id, owner_user_id, created_at
        )
        SELECT organization_id, project_id, resource_type, resource_id, owner_user_id, created_at
        FROM resource_ownership
        """
    )
    connection.execute("DROP TABLE project_members")
    connection.execute("ALTER TABLE project_members_v7 RENAME TO project_members")
    connection.execute("DROP TABLE resource_ownership")
    connection.execute("ALTER TABLE resource_ownership_v7 RENAME TO resource_ownership")
    connection.execute(
        "CREATE INDEX idx_resource_ownership_project "
        "ON resource_ownership (organization_id, project_id, resource_type)"
    )
    violation = connection.execute("PRAGMA foreign_key_check").fetchone()
    if violation is not None:
        raise ValueError("Composite tenant foreign-key migration validation failed")


def _validate_composite_tenant_rows(connection: sqlite3.Connection) -> None:
    checks = (
        """
        SELECT 1 FROM project_members pm
        LEFT JOIN projects p
          ON p.organization_id = pm.organization_id AND p.project_id = pm.project_id
        LEFT JOIN users u
          ON u.organization_id = pm.organization_id AND u.user_id = pm.user_id
        WHERE p.project_id IS NULL OR u.user_id IS NULL LIMIT 1
        """,
        """
        SELECT 1 FROM resource_ownership r
        LEFT JOIN projects p
          ON p.organization_id = r.organization_id AND p.project_id = r.project_id
        LEFT JOIN users u
          ON u.organization_id = r.organization_id AND u.user_id = r.owner_user_id
        WHERE p.project_id IS NULL
           OR (r.owner_user_id IS NOT NULL AND u.user_id IS NULL)
        LIMIT 1
        """,
    )
    if any(connection.execute(query).fetchone() is not None for query in checks):
        raise ValueError("Composite tenant foreign-key pre-migration validation failed")


def _verify_composite_tenant_foreign_keys(connection: sqlite3.Connection) -> None:
    required = {
        "project_members": {
            ("projects", ("organization_id", "project_id"), ("organization_id", "project_id")),
            ("users", ("organization_id", "user_id"), ("organization_id", "user_id")),
        },
        "resource_ownership": {
            ("projects", ("organization_id", "project_id"), ("organization_id", "project_id")),
            ("users", ("organization_id", "owner_user_id"), ("organization_id", "user_id")),
        },
    }
    if current_schema_version(connection) >= 10:
        required["video_jobs"] = {
            ("projects", ("organization_id", "project_id"), ("organization_id", "project_id")),
            ("users", ("organization_id", "owner_user_id"), ("organization_id", "user_id")),
        }
    for table, expected in required.items():
        if not expected <= _foreign_key_signatures(connection, table):
            raise ValueError("Composite tenant foreign-key schema verification failed")


def _foreign_key_signatures(
    connection: sqlite3.Connection,
    table: str,
) -> set[tuple[str, tuple[str, ...], tuple[str, ...]]]:
    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in connection.execute(f"PRAGMA foreign_key_list({table})").fetchall():
        grouped.setdefault(int(row["id"]), []).append(row)
    signatures = set()
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda row: int(row["seq"]))
        signatures.add(
            (
                str(ordered[0]["table"]),
                tuple(str(row["from"]) for row in ordered),
                tuple(str(row["to"]) for row in ordered),
            )
        )
    return signatures


MIGRATIONS: tuple[Migration, ...] = (
    (1, "auth_foundation", _migration_auth_foundation),
    (2, "instruction_lifecycle", _migration_instruction_lifecycle),
    (3, "project_ownership", _migration_project_ownership),
    (4, "admin_lifecycle", _migration_admin_lifecycle),
    (5, "shared_rate_limit", _migration_shared_rate_limit),
    (6, "browser_session_csrf", _migration_browser_session_csrf),
    (7, "composite_tenant_foreign_keys", _migration_composite_tenant_foreign_keys),
    (8, "admin_audit_hash_chain", _migration_admin_audit_hash_chain),
    (9, "session_idle_tracking", _migration_session_idle_tracking),
    (10, "durable_video_jobs", _migration_durable_video_jobs),
)
