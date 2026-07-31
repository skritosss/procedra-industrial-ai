import json
from pathlib import Path
import re
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_TEXT_BYTES = 10 * 1024 * 1024
SECRET_PATTERNS = {
    "openai_api_key": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b"),
    "github_token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "aws_access_key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def main() -> int:
    result = audit_public_content(PROJECT_ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def audit_public_content(project_root: Path) -> dict[str, object]:
    findings: list[dict[str, str]] = []
    oversized_text_files: list[str] = []
    scanned_files = 0
    for relative_path in _candidate_paths(project_root):
        path = project_root / relative_path
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes()
        if b"\0" in content[:8192]:
            continue
        if len(content) > MAX_TEXT_BYTES:
            oversized_text_files.append(relative_path)
            continue
        scanned_files += 1
        for finding_type, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append({"path": relative_path, "type": finding_type})
    return {
        "ok": not findings and not oversized_text_files,
        "scanned_files": scanned_files,
        "findings": findings,
        "oversized_text_files": oversized_text_files,
        "scope": "tracked and non-ignored untracked text files; high-confidence secret patterns only",
    }


def _candidate_paths(project_root: Path) -> list[str]:
    completed = subprocess.run(
        ("git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"),
        cwd=project_root,
        check=True,
        capture_output=True,
    )
    return sorted(path for path in completed.stdout.decode("utf-8").split("\0") if path)


if __name__ == "__main__":
    raise SystemExit(main())
