import argparse
import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (
    PROJECT_ROOT / "generated" / "keyframes",
    PROJECT_ROOT / "uploads" / "videos",
)
PROTECTED_FILENAMES = {".gitkeep", ".gitignore"}
ORGANIZATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class CleanupResult:
    dry_run: bool
    max_age_hours: float
    scanned_files: int
    matched_files: int
    removed_files: int
    removed_dirs: int
    bytes_matched: int
    bytes_removed: int
    roots: list[str]
    files: list[str]
    orphaned_video_ownership_rows: int = 0
    removed_video_ownership_rows: int = 0
    terminal_video_job_rows: int = 0
    removed_terminal_video_job_rows: int = 0


def main() -> None:
    args = _parse_args()
    result = cleanup_artifacts(
        roots=tuple(args.root) if args.root else DEFAULT_ROOTS,
        max_age_hours=args.max_age_hours,
        delete=args.delete,
        reconcile_video_ownership=args.reconcile_video_ownership,
        database_path=args.database,
    )
    payload = asdict(result)
    if not args.show_files and len(result.files) > args.file_limit:
        payload["files"] = result.files[: args.file_limit]
        payload["files_truncated"] = len(result.files) - args.file_limit
    else:
        payload["files_truncated"] = 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cleanup_artifacts(
    *,
    roots: tuple[Path, ...] = DEFAULT_ROOTS,
    max_age_hours: float = 24,
    delete: bool = False,
    reconcile_video_ownership: bool = False,
    database_path: Path | None = None,
    now: datetime | None = None,
) -> CleanupResult:
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be greater than 0")

    safe_roots = tuple(_safe_root(root) for root in roots)
    cutoff = (now or datetime.now(UTC)) - timedelta(hours=max_age_hours)
    resolved_database_path = database_path or _default_database_path()
    active_job_artifacts = _active_video_job_artifact_paths(resolved_database_path)
    matched_files: list[Path] = []
    scanned_files = 0
    bytes_matched = 0
    bytes_removed = 0
    removed_files = 0

    for root in safe_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file() or path.name in PROTECTED_FILENAMES:
                continue
            scanned_files += 1
            if path.resolve() in active_job_artifacts:
                continue
            stat = path.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, UTC)
            if modified > cutoff:
                continue
            matched_files.append(path)
            bytes_matched += stat.st_size
            if delete:
                bytes_removed += stat.st_size
                path.unlink()
                removed_files += 1

    removed_dirs = _remove_empty_dirs(safe_roots) if delete else 0
    orphaned_rows = 0
    removed_rows = 0
    if reconcile_video_ownership:
        orphaned_rows, removed_rows = _reconcile_video_ownership(
            resolved_database_path,
            delete=delete,
        )
    terminal_jobs, removed_terminal_jobs = _reconcile_terminal_video_jobs(
        resolved_database_path,
        cutoff=cutoff,
        delete=delete,
    )
    return CleanupResult(
        dry_run=not delete,
        max_age_hours=max_age_hours,
        scanned_files=scanned_files,
        matched_files=len(matched_files),
        removed_files=removed_files,
        removed_dirs=removed_dirs,
        bytes_matched=bytes_matched,
        bytes_removed=bytes_removed,
        roots=[str(root.relative_to(PROJECT_ROOT)) for root in safe_roots],
        files=[str(path.relative_to(PROJECT_ROOT)) for path in matched_files],
        orphaned_video_ownership_rows=orphaned_rows,
        removed_video_ownership_rows=removed_rows,
        terminal_video_job_rows=terminal_jobs,
        removed_terminal_video_job_rows=removed_terminal_jobs,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean old generated/uploaded runtime artifacts.")
    parser.add_argument("--max-age-hours", type=float, default=24, help="Delete files older than this age.")
    parser.add_argument("--delete", action="store_true", help="Actually delete matched files. Default is dry-run.")
    parser.add_argument(
        "--reconcile-video-ownership",
        action="store_true",
        help="Report ownership rows whose video/keyframe artifacts no longer exist; remove them with --delete.",
    )
    parser.add_argument("--database", type=Path, help="Application database used for ownership reconciliation.")
    parser.add_argument("--show-files", action="store_true", help="Print every matched file instead of a compact preview.")
    parser.add_argument("--file-limit", type=int, default=20, help="Number of matched files to show unless --show-files is used.")
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        help="Artifact root to scan. Defaults to generated/ and uploads/. Must be inside the project.",
    )
    args = parser.parse_args()
    if args.file_limit < 0:
        parser.error("--file-limit must be greater than or equal to 0")
    return args


def _default_database_path() -> Path:
    configured = os.getenv("DATABASE_PATH", "generated/app.sqlite3")
    path = Path(configured)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _reconcile_video_ownership(database_path: Path, *, delete: bool) -> tuple[int, int]:
    path = database_path.resolve()
    if not path.is_file():
        return 0, 0
    uri = f"file:{path}?mode={'rw' if delete else 'ro'}"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'resource_ownership'"
        ).fetchone()
        if table is None:
            return 0, 0
        rows = connection.execute(
            """
            SELECT organization_id, resource_id FROM resource_ownership
            WHERE resource_type = 'video'
            """
        ).fetchall()
        orphaned = [
            (str(row["organization_id"]), str(row["resource_id"]))
            for row in rows
            if not _video_artifacts_exist(str(row["organization_id"]), str(row["resource_id"]))
        ]
        if not delete or not orphaned:
            return len(orphaned), 0
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            """
            DELETE FROM resource_ownership
            WHERE organization_id = ? AND resource_type = 'video' AND resource_id = ?
            """,
            orphaned,
        )
        connection.commit()
    return len(orphaned), len(orphaned)


def _video_artifacts_exist(organization_id: str, video_id: str) -> bool:
    if not ORGANIZATION_ID_PATTERN.fullmatch(organization_id):
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", video_id):
        return False
    keyframe_root = PROJECT_ROOT / "generated" / "keyframes"
    upload_root = PROJECT_ROOT / "uploads" / "videos"
    if organization_id != "legacy":
        keyframe_root /= organization_id
        upload_root /= organization_id
    keyframe_dir = keyframe_root / video_id
    if keyframe_dir.is_dir() and any(
        path.is_file() and not path.is_symlink() for path in keyframe_dir.iterdir()
    ):
        return True
    return any(path.is_file() and not path.is_symlink() for path in upload_root.glob(f"{video_id}.*"))


def _active_video_job_artifact_paths(database_path: Path) -> set[Path]:
    path = database_path.resolve()
    if not path.is_file():
        return set()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'video_jobs'"
        ).fetchone()
        if table is None:
            return set()
        rows = connection.execute(
            """
            SELECT artifact_path FROM video_jobs
            WHERE status IN ('queued', 'running') AND artifact_path IS NOT NULL
            """
        ).fetchall()
    return {Path(str(row[0])).resolve() for row in rows}


def _reconcile_terminal_video_jobs(
    database_path: Path,
    *,
    cutoff: datetime,
    delete: bool,
) -> tuple[int, int]:
    path = database_path.resolve()
    if not path.is_file():
        return 0, 0
    uri = f"file:{path}?mode={'rw' if delete else 'ro'}"
    with sqlite3.connect(uri, uri=True) as connection:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'video_jobs'"
        ).fetchone()
        if table is None:
            return 0, 0
        rows = connection.execute(
            """
            SELECT job_id FROM video_jobs
            WHERE status IN ('succeeded', 'failed', 'cancelled')
              AND completed_at IS NOT NULL AND completed_at <= ?
            """,
            (cutoff.isoformat(),),
        ).fetchall()
        job_ids = [(str(row[0]),) for row in rows]
        if not delete or not job_ids:
            return len(job_ids), 0
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany("DELETE FROM video_jobs WHERE job_id = ?", job_ids)
        connection.commit()
    return len(job_ids), len(job_ids)


def _safe_root(root: Path) -> Path:
    resolved = root.resolve()
    project = PROJECT_ROOT.resolve()
    if resolved == project:
        raise ValueError("Refusing to clean the project root directly")
    try:
        resolved.relative_to(project)
    except ValueError as exc:
        raise ValueError("Cleanup root must be inside the project") from exc
    return resolved


def _remove_empty_dirs(roots: tuple[Path, ...]) -> int:
    removed = 0
    for root in roots:
        if not root.exists():
            continue
        directories = sorted(
            (path for path in root.rglob("*") if not path.is_symlink() and path.is_dir()),
            key=lambda item: len(item.parts),
            reverse=True,
        )
        for directory in directories:
            if any(directory.iterdir()):
                continue
            directory.rmdir()
            removed += 1
    return removed


if __name__ == "__main__":
    main()
