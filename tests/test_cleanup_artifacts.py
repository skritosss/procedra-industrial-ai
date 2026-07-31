from datetime import UTC, datetime, timedelta
import os
import sqlite3
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


def test_cleanup_reconciles_video_ownership_only_after_artifacts_are_gone(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    database_path = tmp_path / "generated" / "app.sqlite3"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE resource_ownership (
                organization_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO resource_ownership VALUES (?, 'video', ?)",
            [("legacy", "missing-video"), ("tenant-a", "present-video")],
        )
    present = tmp_path / "generated" / "keyframes" / "tenant-a" / "present-video" / "frame.jpg"
    _touch(present, datetime.now(UTC))

    planned = cleanup.cleanup_artifacts(
        roots=(tmp_path / "generated" / "keyframes",),
        reconcile_video_ownership=True,
        database_path=database_path,
    )
    assert planned.orphaned_video_ownership_rows == 1
    assert planned.removed_video_ownership_rows == 0

    applied = cleanup.cleanup_artifacts(
        roots=(tmp_path / "generated" / "keyframes",),
        delete=True,
        reconcile_video_ownership=True,
        database_path=database_path,
    )
    assert applied.orphaned_video_ownership_rows == 1
    assert applied.removed_video_ownership_rows == 1
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute("SELECT organization_id, resource_id FROM resource_ownership").fetchall()
    assert rows == [("tenant-a", "present-video")]


def test_cleanup_default_roots_do_not_target_saved_instructions_or_documents() -> None:
    default_roots = {root.relative_to(cleanup.PROJECT_ROOT).as_posix() for root in cleanup.DEFAULT_ROOTS}

    assert default_roots == {"generated/keyframes", "uploads/videos"}


def test_cleanup_preserves_active_job_artifact_and_removes_old_terminal_job(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cleanup, "PROJECT_ROOT", tmp_path)
    now = datetime(2026, 7, 16, tzinfo=UTC)
    database_path = tmp_path / "generated" / "app.sqlite3"
    database_path.parent.mkdir(parents=True)
    active_artifact = tmp_path / "uploads" / "videos" / "active.mp4"
    terminal_artifact = tmp_path / "uploads" / "videos" / "terminal.mp4"
    _touch(active_artifact, now - timedelta(days=3))
    _touch(terminal_artifact, now - timedelta(days=3))
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE video_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                artifact_path TEXT,
                completed_at TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO video_jobs VALUES (?, ?, ?, ?)",
            [
                ("active", "running", str(active_artifact), None),
                ("terminal", "succeeded", str(terminal_artifact), (now - timedelta(days=2)).isoformat()),
            ],
        )

    result = cleanup.cleanup_artifacts(
        roots=(tmp_path / "uploads" / "videos",),
        max_age_hours=24,
        delete=True,
        database_path=database_path,
        now=now,
    )

    assert active_artifact.exists()
    assert not terminal_artifact.exists()
    assert result.matched_files == 1
    assert result.terminal_video_job_rows == 1
    assert result.removed_terminal_video_job_rows == 1
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT job_id FROM video_jobs").fetchall() == [("active",)]


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
