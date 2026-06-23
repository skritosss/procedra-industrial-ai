import re
from pathlib import Path


LEGACY_ORGANIZATION_ID = "legacy"
ORGANIZATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def organization_storage_path(root: Path, organization_id: str) -> Path:
    if not ORGANIZATION_ID_PATTERN.fullmatch(organization_id):
        raise ValueError("Invalid organization identifier")
    if organization_id == LEGACY_ORGANIZATION_ID:
        return root
    resolved_root = root.resolve(strict=False)
    candidate = root / organization_id
    try:
        candidate.resolve(strict=False).relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Organization storage path escapes its configured root") from exc
    return candidate
