from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_GITIGNORE_ENTRIES = (
    ".env",
    ".env.*",
    "!.env.example",
    ".DS_Store",
    "generated/",
    "uploads/",
    "outputs/",
    "output/",
    "tmp/",
    "PROJECT_HANDOFF.md",
    "PRODUCT_ROADMAP.md",
    "AUDIT_2026-07-29.md",
    "_internal/",
    "_to_delete/",
    "reports/",
    "docs/Предметная_часть_пилотного_хоздоговора_Procedra.md",
    "docs/ssrn_status_and_outreach_2026-07-29.md",
    "docs/ARTICLE_CHAT.md",
    "docs/article_review_and_roadmap.md",
    "docs/research/*",
)
REQUIRED_DOCKERIGNORE_ENTRIES = (
    ".env",
    ".env.*",
    "!.env.example",
    ".DS_Store",
    "generated/",
    "uploads/",
    "outputs/",
    "output/",
    "tmp/",
    "reports/",
    "PROJECT_HANDOFF.md",
    "PRODUCT_ROADMAP.md",
    "AUDIT_2026-07-29.md",
    "_internal/",
    "_to_delete/",
    "docs/Предметная_часть_пилотного_хоздоговора_Procedra.md",
    "docs/ssrn_status_and_outreach_2026-07-29.md",
    "docs/ARTICLE_CHAT.md",
    "docs/article_review_and_roadmap.md",
    "docs/research/",
)
RESEARCH_ROOT = "docs/research/"
RESEARCH_PUBLIC_ALLOWLIST = (
    "docs/research/README.md",
    "docs/research/procedra_ssrn_submission_package.md",
    "docs/research/procedra_ssrn_working_paper.md",
    "docs/research/procedra_ssrn_working_paper.pdf",
    "docs/research/procedra_ssrn_working_paper_pdf_ready.md",
)
PRIVATE_PATH_PREFIXES = (
    ".env",
    "generated/",
    "uploads/",
    "outputs/",
    "output/",
    "tmp/",
    "reports/",
    ".DS_Store",
    "PROJECT_HANDOFF.md",
    "PRODUCT_ROADMAP.md",
    "AUDIT_2026-07-29.md",
    "_internal/",
    "_to_delete/",
    "docs/Предметная_часть_пилотного_хоздоговора_Procedra.md",
    "docs/ssrn_status_and_outreach_2026-07-29.md",
    "docs/ARTICLE_CHAT.md",
    "docs/article_review_and_roadmap.md",
)
IGNORED_ARTIFACT_ROOTS = (
    PROJECT_ROOT / "generated",
    PROJECT_ROOT / "uploads",
    PROJECT_ROOT / "reports",
    PROJECT_ROOT / "outputs",
    PROJECT_ROOT / "output",
    PROJECT_ROOT / "tmp",
)
PROTECTED_PUBLIC_ENV = ".env.example"


@dataclass
class ArtifactSummary:
    path: str
    exists: bool
    files: int = 0
    bytes: int = 0
    samples: list[str] | None = None


@dataclass
class PublicScopeAudit:
    ok: bool
    gitignore_missing_entries: list[str]
    dockerignore_missing_entries: list[str]
    tracked_private_paths: list[str]
    dry_run_private_paths: list[str]
    dry_run_paths: list[str]
    ignored_artifacts: list[ArtifactSummary]


def main() -> None:
    args = _parse_args()
    result = audit_public_scope(project_root=PROJECT_ROOT, sample_limit=args.sample_limit)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if not result.ok:
        raise SystemExit(1)


def audit_public_scope(*, project_root: Path, sample_limit: int = 0) -> PublicScopeAudit:
    gitignore_entries = _ignore_entries(project_root / ".gitignore")
    gitignore_missing_entries = [entry for entry in REQUIRED_GITIGNORE_ENTRIES if entry not in gitignore_entries]
    dockerignore_entries = _ignore_entries(project_root / ".dockerignore")
    dockerignore_missing_entries = [
        entry for entry in REQUIRED_DOCKERIGNORE_ENTRIES if entry not in dockerignore_entries
    ]
    tracked_paths = _git_paths(project_root, ("ls-files", "-z"))
    dry_run_paths = _git_add_dry_run_paths(project_root)
    tracked_private_paths = [path for path in tracked_paths if _is_private_path(path)]
    dry_run_private_paths = [path for path in dry_run_paths if _is_private_path(path)]
    ignored_artifacts = [
        summarize_artifacts(root, project_root=project_root, sample_limit=sample_limit)
        for root in IGNORED_ARTIFACT_ROOTS
    ]
    return PublicScopeAudit(
        ok=not gitignore_missing_entries
        and not dockerignore_missing_entries
        and not tracked_private_paths
        and not dry_run_private_paths,
        gitignore_missing_entries=gitignore_missing_entries,
        dockerignore_missing_entries=dockerignore_missing_entries,
        tracked_private_paths=tracked_private_paths,
        dry_run_private_paths=dry_run_private_paths,
        dry_run_paths=dry_run_paths,
        ignored_artifacts=ignored_artifacts,
    )


def summarize_artifacts(root: Path, *, project_root: Path, sample_limit: int = 5) -> ArtifactSummary:
    relative_root = _relative_posix(root, project_root)
    if not root.exists():
        return ArtifactSummary(path=relative_root, exists=False, samples=[])
    files = 0
    total_bytes = 0
    samples: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        files += 1
        total_bytes += path.stat().st_size
        if len(samples) < sample_limit:
            samples.append(_relative_posix(path, project_root))
    return ArtifactSummary(path=relative_root, exists=True, files=files, bytes=total_bytes, samples=samples)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Git path scope before publication; this does not scan allowed file contents."
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=0,
        help="Opt in to local-only sample filenames from ignored artifact roots (default: 0).",
    )
    args = parser.parse_args()
    if args.sample_limit < 0:
        parser.error("--sample-limit must be greater than or equal to 0")
    return args


def _ignore_entries(path: Path) -> set[str]:
    """Read the meaningful lines of a .gitignore-style file.

    Both boundaries matter and they are not the same. `.gitignore` decides what
    reaches the public repository; `.dockerignore` decides what reaches the image
    a customer receives. The audit used to watch only the first, which is why
    `COPY docs ./docs` shipped the contract draft without anything objecting.
    """
    if not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def _git_paths(project_root: Path, args: tuple[str, ...]) -> list[str]:
    completed = subprocess.run(("git", *args), cwd=project_root, check=True, capture_output=True)
    return [path.decode("utf-8") for path in completed.stdout.split(b"\0") if path]


def _git_add_dry_run_paths(project_root: Path) -> list[str]:
    index_location = subprocess.run(
        ("git", "rev-parse", "--git-path", "index"),
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_index = Path(index_location)
    if not source_index.is_absolute():
        source_index = project_root / source_index
    with tempfile.TemporaryDirectory(prefix="procedra-public-scope-") as temporary_dir:
        temporary_index = Path(temporary_dir) / "index"
        environment = {**os.environ, "GIT_INDEX_FILE": str(temporary_index)}
        if source_index.is_file():
            shutil.copyfile(source_index, temporary_index)
        else:
            subprocess.run(
                ("git", "read-tree", "HEAD"),
                cwd=project_root,
                check=True,
                capture_output=True,
                env=environment,
            )
        completed = subprocess.run(
            ("git", "add", "--dry-run", "."),
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
    paths: list[str] = []
    for line in completed.stdout.splitlines():
        parts = shlex.split(line)
        if len(parts) >= 2:
            paths.append(parts[-1])
    return sorted(paths)


def _is_private_path(path: str) -> bool:
    if path == PROTECTED_PUBLIC_ENV:
        return False
    if path == ".DS_Store" or path.endswith("/.DS_Store"):
        return True
    if path.startswith(RESEARCH_ROOT):
        # Research notes are private unless explicitly published, so a new file
        # added to that directory fails closed instead of leaking silently.
        return path not in RESEARCH_PUBLIC_ALLOWLIST
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in PRIVATE_PATH_PREFIXES)


def _relative_posix(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
