from __future__ import annotations

import io
import sys
import threading

import pytest

from app.schemas.video import VideoKeyframeResponse
from app.workers import stage_process


class _BlockingProcess:
    def __init__(self) -> None:
        self.stdin = io.BytesIO()
        self.returncode = None
        self.stopped = False

    def poll(self):
        return self.returncode


def test_isolated_analyze_stage_round_trips_valid_response() -> None:
    response = VideoKeyframeResponse(
        video_id="video-stage-test",
        original_filename="sample.mp4",
        frame_count=0,
        fps=0,
        duration_seconds=0,
    )

    result = stage_process.run_isolated_stage(
        "analyze",
        {"response": response.model_dump(mode="json"), "source_kind": "upload"},
        timeout_seconds=10,
        poll_seconds=0.05,
        interrupt_reason=lambda: None,
    )

    assert VideoKeyframeResponse.model_validate(result).video_id == "video-stage-test"


def test_isolated_stage_hard_timeout_stops_child(monkeypatch) -> None:
    process = _BlockingProcess()
    monkeypatch.setattr(stage_process.subprocess, "Popen", lambda *_args, **_kwargs: process)

    def stop(target) -> None:
        target.stopped = True
        target.returncode = -15

    monkeypatch.setattr(stage_process, "_stop_process", stop)

    with pytest.raises(stage_process.StageTimeoutError):
        stage_process.run_isolated_stage(
            "extract",
            {},
            timeout_seconds=0.001,
            poll_seconds=0.001,
            interrupt_reason=lambda: None,
        )

    assert process.stopped is True


def test_isolated_stage_cancellation_stops_child(monkeypatch) -> None:
    process = _BlockingProcess()
    monkeypatch.setattr(stage_process.subprocess, "Popen", lambda *_args, **_kwargs: process)

    def stop(target) -> None:
        target.stopped = True
        target.returncode = -15

    monkeypatch.setattr(stage_process, "_stop_process", stop)

    with pytest.raises(stage_process.StageInterruptedError, match="cancelled"):
        stage_process.run_isolated_stage(
            "extract",
            {},
            timeout_seconds=10,
            poll_seconds=0.05,
            interrupt_reason=lambda: "cancelled",
        )

    assert process.stopped is True


def test_large_request_does_not_block_before_the_stage_deadline(tmp_path, monkeypatch) -> None:
    # A child that never drains stdin. The pipe buffer is 64 KB and a stage
    # request may reach 1 MB, so writing inline blocked the parent forever —
    # before the deadline loop had even started.
    stub = tmp_path / "deaf_child.py"
    stub.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    monkeypatch.setattr(
        stage_process, "STAGE_RUNNER_COMMAND", (sys.executable, str(stub))
    )
    payload = {"blob": "x" * (1024 * 1024)}
    outcome: list[object] = []

    def call() -> None:
        try:
            stage_process.run_isolated_stage(
                "download",
                payload,
                timeout_seconds=2.0,
                poll_seconds=0.1,
                interrupt_reason=lambda: None,
            )
        except BaseException as error:  # noqa: BLE001 - recorded for the assertion
            outcome.append(error)

    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    worker.join(timeout=30)

    # Without the fix this thread is still stuck in write() and join times out.
    assert not worker.is_alive(), "run_isolated_stage blocked writing to stdin"
    assert outcome and isinstance(outcome[0], stage_process.StageTimeoutError)


def test_cancellation_still_works_while_the_request_is_being_written(tmp_path, monkeypatch) -> None:
    stub = tmp_path / "deaf_child_cancel.py"
    stub.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    monkeypatch.setattr(
        stage_process, "STAGE_RUNNER_COMMAND", (sys.executable, str(stub))
    )
    payload = {"blob": "x" * (1024 * 1024)}
    outcome: list[object] = []

    def call() -> None:
        try:
            stage_process.run_isolated_stage(
                "download",
                payload,
                timeout_seconds=60.0,
                poll_seconds=0.1,
                interrupt_reason=lambda: "cancelled",
            )
        except BaseException as error:  # noqa: BLE001 - recorded for the assertion
            outcome.append(error)

    worker = threading.Thread(target=call, daemon=True)
    worker.start()
    worker.join(timeout=30)

    # Moving the write off the main path must not cost cancellation, which is
    # what `communicate()` would have taken away.
    assert not worker.is_alive()
    assert outcome and isinstance(outcome[0], stage_process.StageInterruptedError)


def test_failed_stage_reports_why_it_failed(tmp_path, monkeypatch) -> None:
    stub = tmp_path / "noisy_failure.py"
    stub.write_text(
        "import sys\n"
        "sys.stdin.read()\n"
        "print('ffmpeg: codec not supported\\x1b[31m', file=sys.stderr)\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stage_process, "STAGE_RUNNER_COMMAND", (sys.executable, str(stub)))

    with pytest.raises(stage_process.StageExecutionError) as failure:
        stage_process.run_isolated_stage(
            "download",
            {"video": "x"},
            timeout_seconds=20.0,
            poll_seconds=0.1,
            interrupt_reason=lambda: None,
        )

    # The stderr file was written and never read, so every failure collapsed into
    # "stage failed" with nothing to act on.
    assert "codec not supported" in failure.value.details
    # Control characters must not travel from a child process into the log.
    assert "\x1b" not in failure.value.details


def test_a_child_flooding_stderr_is_stopped(tmp_path, monkeypatch) -> None:
    stub = tmp_path / "flooding.py"
    stub.write_text(
        "import sys, time\n"
        "sys.stdin.read()\n"
        "chunk = 'x' * 65536\n"
        "end = time.monotonic() + 30\n"
        "while time.monotonic() < end:\n"
        "    print(chunk, file=sys.stderr)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stage_process, "STAGE_RUNNER_COMMAND", (sys.executable, str(stub)))
    monkeypatch.setattr(stage_process, "MAX_STAGE_STDERR_FILE_BYTES", 256 * 1024)

    with pytest.raises(stage_process.StageExecutionError) as failure:
        stage_process.run_isolated_stage(
            "download",
            {"video": "x"},
            timeout_seconds=60.0,
            poll_seconds=0.05,
            interrupt_reason=lambda: None,
        )

    # Without a cap the file grows until the disk does, and the stage deadline
    # has not expired yet.
    assert "too much to stderr" in failure.value.details
