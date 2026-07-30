from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_STAGE_RESULT_BYTES = 5 * 1024 * 1024
PROCESS_TERMINATE_GRACE_SECONDS = 2.0


class StageTimeoutError(RuntimeError):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"Video job stage timed out: {stage}")


class StageInterruptedError(RuntimeError):
    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"Video job stage interrupted: {stage} ({reason})")


class StageExecutionError(RuntimeError):
    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"Video job stage failed: {stage}")


def run_isolated_stage(
    stage: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
    poll_seconds: float,
    interrupt_reason: Callable[[], str | None],
) -> dict[str, Any]:
    request_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    deadline = time.monotonic() + timeout_seconds
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.workers.video_stage_runner", stage],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=os.name == "posix",
        )
        try:
            assert process.stdin is not None
            process.stdin.write(request_bytes)
            process.stdin.close()
            while process.poll() is None:
                reason = interrupt_reason()
                if reason is not None:
                    _stop_process(process)
                    raise StageInterruptedError(stage, reason)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _stop_process(process)
                    raise StageTimeoutError(stage)
                time.sleep(min(poll_seconds, remaining))
        except BaseException:
            if process.poll() is None:
                _stop_process(process)
            raise

        if process.returncode != 0:
            raise StageExecutionError(stage)
        stdout_file.seek(0)
        raw_result = stdout_file.read(MAX_STAGE_RESULT_BYTES + 1)
        if len(raw_result) > MAX_STAGE_RESULT_BYTES:
            raise StageExecutionError(stage)
        try:
            envelope = json.loads(raw_result)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise StageExecutionError(stage) from None
        if not isinstance(envelope, dict):
            raise StageExecutionError(stage)
        if envelope.get("ok") is True and isinstance(envelope.get("result"), dict):
            return envelope["result"]
        if envelope.get("error_type") == "value_error" and isinstance(envelope.get("message"), str):
            raise ValueError(envelope["message"])
        raise StageExecutionError(stage)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    _signal_process(process, signal.SIGTERM)
    try:
        process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    _signal_process(process, signal.SIGKILL)
    process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)


def _signal_process(process: subprocess.Popen[bytes], sig: signal.Signals) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, sig)
        elif sig == signal.SIGTERM:
            process.terminate()
        else:
            process.kill()
    except ProcessLookupError:
        return
