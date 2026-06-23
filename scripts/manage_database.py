import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import get_settings  # noqa: E402
from app.storage.database import (  # noqa: E402
    apply_migrations,
    backup_database,
    connect_database,
    restore_database,
    verify_database,
)


def main() -> None:
    args = _parse_args()
    database_path = args.database or get_settings().database_path
    if args.command == "migrate":
        with connect_database(database_path) as connection:
            version = apply_migrations(
                connection,
                session_ttl_seconds=get_settings().auth_session_ttl_seconds,
            )
        result = {"status": "ok", "database": str(database_path), "schema_version": version}
    elif args.command == "verify":
        result = {"database": str(database_path), **verify_database(database_path)}
    elif args.command == "backup":
        destination = args.output or _default_backup_path(database_path)
        backup_database(database_path, destination)
        result = {"database": str(database_path), "backup": str(destination), **verify_database(destination)}
    else:
        if args.source is None:
            raise ValueError("--source is required for restore")
        safety_backup = args.safety_backup
        if database_path.exists() and safety_backup is None:
            safety_backup = _default_safety_backup_path(database_path)
        restore_database(args.source, database_path, safety_backup_path=safety_backup)
        result = {
            "database": str(database_path),
            "restored_from": str(args.source),
            "safety_backup": str(safety_backup) if safety_backup else None,
            **verify_database(database_path),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the Procedra SQLite database.")
    parser.add_argument("command", choices=("migrate", "verify", "backup", "restore"))
    parser.add_argument("--database", type=Path, help="Database path; defaults to DATABASE_PATH.")
    parser.add_argument("--output", type=Path, help="Backup destination for the backup command.")
    parser.add_argument("--source", type=Path, help="Verified backup source for the restore command.")
    parser.add_argument(
        "--safety-backup",
        type=Path,
        help="Pre-restore backup path. A timestamped path is generated when the target exists.",
    )
    return parser.parse_args()


def _default_backup_path(database_path: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return database_path.parent / "backups" / f"{database_path.stem}-{timestamp}.sqlite3"


def _default_safety_backup_path(database_path: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return database_path.parent / "backups" / f"{database_path.stem}-pre-restore-{timestamp}.sqlite3"


if __name__ == "__main__":
    main()
