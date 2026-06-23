import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import get_settings  # noqa: E402
from app.storage.document_reconciliation import reconcile_document_ownership  # noqa: E402


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    result = reconcile_document_ownership(
        database_path=args.database or settings.database_path,
        documents_root=args.documents_root or PROJECT_ROOT / "uploads" / "documents",
        apply=args.apply,
    )
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    if result.blocked_by_issues:
        raise SystemExit(2)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile document files with resource ownership. Default is dry-run."
    )
    parser.add_argument("--database", type=Path, help="Database path; defaults to DATABASE_PATH.")
    parser.add_argument(
        "--documents-root",
        type=Path,
        help="Document root; defaults to uploads/documents inside the project.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Atomically register the clean plan. Without this flag no ownership rows are written.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
