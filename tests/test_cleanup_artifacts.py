from datetime import UTC, datetime, timedelta
import os
import sys

import pytest

from scripts import cleanup_artifacts as cleanup


def _touch(path, modified: datetime, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    timestamp = modified.timestamp()
    os.utime(path, (timestamp, timestamp))


def test_cleanup_artifacts_dry_run_does_not_delete_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    now = datetime(2026, 6, 12, tzinfo=UTC)
    old_file = tmp_path / "generated" / "keyframes" / "old" / "frame.jpg"
    fresh_file = tmp_path / "generated" / "keyframes" / "fresh" / "frame.jpg"
    _touch(old_file, now - timedelta(hours=48))
    _touch(fresh_file, now - timedelta(hours=1))

    result = cleanup.cleanup_artifacts(roots=(tmp_path / "generated",), max_age_hours=24, delete=False, now=now)

    assert result.dry_run is True
    assert result.scanned_files == 2
    assert result.matched_files == 1
    assert result.removed_files == 0
    assert old_file.exists()
    assert fresh_file.exists()
    assert result.files == ["generated/keyframes/old/frame.jpg"]


def test_cleanup_artifacts_delete_removes_old_files_and_empty_dirs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    now = datetime(2026, 6, 12, tzinfo=UTC)
    old_file = tmp_path / "uploads" / "videos" / "old.mp4"
    fresh_file = tmp_path / "uploads" / "videos" / "fresh.mp4"
    _touch(old_file, now - timedelta(hours=72), b"old")
    _touch(fresh_file, now - timedelta(minutes=30), b"fresh")

    result = cleanup.cleanup_artifacts(roots=(tmp_path / "uploads",), max_age_hours=24, delete=True, now=now)

    assert result.dry_run is False
    assert result.matched_files == 1
    assert result.removed_files == 1
    assert result.bytes_removed == 3
    assert not old_file.exists()
    assert fresh_file.exists()


def test_cleanup_default_roots_do_not_target_saved_instructions_or_documents() -> None:
    default_roots = {root.relative_to(cleanup.PROJECT_ROOT).as_posix() for root in cleanup.DEFAULT_ROOTS}

    assert default_roots == {"generated/keyframes", "uploads/videos"}


def test_cleanup_artifacts_preserves_protected_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    now = datetime(2026, 6, 12, tzinfo=UTC)
    protected = tmp_path / "generated" / ".gitkeep"
    _touch(protected, now - timedelta(days=10))

    result = cleanup.cleanup_artifacts(roots=(tmp_path / "generated",), max_age_hours=24, delete=True, now=now)

    assert result.scanned_files == 0
    assert protected.exists()


def test_cleanup_artifacts_skips_symlinks(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    now = datetime(2026, 6, 12, tzinfo=UTC)
    outside = tmp_path / "outside.txt"
    _touch(outside, now - timedelta(days=10), b"outside")
    link = tmp_path / "generated" / "linked-outside.txt"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)

    result = cleanup.cleanup_artifacts(roots=(tmp_path / "generated",), max_age_hours=24, delete=True, now=now)

    assert result.scanned_files == 0
    assert result.matched_files == 0
    assert link.exists()
    assert outside.exists()


def test_cleanup_artifacts_rejects_roots_outside_project(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path / "project")

    with pytest.raises(ValueError, match="inside the project"):
        cleanup.cleanup_artifacts(roots=(tmp_path / "outside",), max_age_hours=24)


def test_cleanup_artifacts_rejects_project_root(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", project)

    with pytest.raises(ValueError, match="project root"):
        cleanup.cleanup_artifacts(roots=(project,), max_age_hours=24)


def test_cleanup_artifacts_rejects_non_positive_age(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)

    with pytest.raises(ValueError, match="greater than 0"):
        cleanup.cleanup_artifacts(roots=(tmp_path / "generated",), max_age_hours=0)


def test_cleanup_artifacts_cli_compacts_long_file_list(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    now = datetime.now(UTC) - timedelta(hours=48)
    for index in range(3):
        _touch(tmp_path / "generated" / f"file_{index}.txt", now)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cleanup_artifacts.py",
            "--root",
            str(tmp_path / "generated"),
            "--max-age-hours",
            "24",
            "--file-limit",
            "1",
        ],
    )

    cleanup.main()
    output = capsys.readouterr().out

    assert '"matched_files": 3' in output
    assert '"files_truncated": 2' in output


def test_cleanup_artifacts_cli_rejects_negative_file_limit(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["cleanup_artifacts.py", "--file-limit", "-1"])

    with pytest.raises(SystemExit):
        cleanup.main()
