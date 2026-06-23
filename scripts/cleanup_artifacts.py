import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (
    PROJECT_ROOT / "generated" / "keyframes",
    PROJECT_ROOT / "uploads" / "videos",
)
PROTECTED_FILENAMES = {".gitkeep", ".gitignore"}


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


def main() -> None:
    args = _parse_args()
    result = cleanup_artifacts(
        roots=tuple(args.root) if args.root else DEFAULT_ROOTS,
        max_age_hours=args.max_age_hours,
        delete=args.delete,
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
    now: datetime | None = None,
) -> CleanupResult:
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be greater than 0")

    safe_roots = tuple(_safe_root(root) for root in roots)
    cutoff = (now or datetime.now(UTC)) - timedelta(hours=max_age_hours)
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
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean old generated/uploaded runtime artifacts.")
    parser.add_argument("--max-age-hours", type=float, default=24, help="Delete files older than this age.")
    parser.add_argument("--delete", action="store_true", help="Actually delete matched files. Default is dry-run.")
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
