from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_STAGE_RESULT_BYTES = 5 * 1024 * 1024
PROCESS_TERMINATE_GRACE_SECONDS = 2.0
STAGE_RUNNER_COMMAND = (sys.executable, "-m", "app.workers.video_stage_runner")
MAX_STAGE_STDERR_BYTES = 8 * 1024
MAX_STAGE_STDERR_FILE_BYTES = 4 * 1024 * 1024


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
    def __init__(self, stage: str, details: str = "") -> None:
        self.stage = stage
        self.details = details
        message = f"Video job stage failed: {stage}"
        if details:
            message = f"{message}: {details}"
        super().__init__(message)


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
            [*STAGE_RUNNER_COMMAND, stage],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=os.name == "posix",
        )
        # Hand the payload over on a separate thread. Writing it inline blocked
        # before the deadline loop below had started: a pipe holds 64 KB, a stage
        # request may reach 1 MB, and a child that does not drain stdin
        # immediately left the parent stuck in write() forever. Nothing timed
        # that out — the stage deadline had not begun — so the job lease expired,
        # the job was retried, and it hung again, with nothing in the log.
        #
        # `communicate()` would also cover the write, but it waits for the whole
        # process and would discard cancellation and lease renewal.
        writer = threading.Thread(
            target=_write_request,
            args=(process, request_bytes),
            name=f"stage-stdin-{stage}",
            daemon=True,
        )
        writer.start()
        try:
            while process.poll() is None:
                reason = interrupt_reason()
                if reason is not None:
                    _stop_process(process)
                    raise StageInterruptedError(stage, reason)
                if _file_size(stderr_file) > MAX_STAGE_STDERR_FILE_BYTES:
                    # A child looping on an error message would otherwise fill
                    # the disk while the stage deadline has not expired yet.
                    _stop_process(process)
                    raise StageExecutionError(stage, "stage wrote too much to stderr")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    _stop_process(process)
                    raise StageTimeoutError(stage)
                time.sleep(min(poll_seconds, remaining))
        except BaseException:
            if process.poll() is None:
                _stop_process(process)
            raise
        finally:
            # Killing the child breaks the pipe, so a blocked write returns.
            writer.join(timeout=PROCESS_TERMINATE_GRACE_SECONDS)

        if process.returncode != 0:
            raise StageExecutionError(stage, _stderr_tail(stderr_file))
        stdout_file.seek(0)
        raw_result = stdout_file.read(MAX_STAGE_RESULT_BYTES + 1)
        if len(raw_result) > MAX_STAGE_RESULT_BYTES:
            raise StageExecutionError(stage)
        try:
            envelope = json.loads(raw_result)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise StageExecutionError(stage, _stderr_tail(stderr_file)) from None
        if not isinstance(envelope, dict):
            raise StageExecutionError(stage, _stderr_tail(stderr_file))
        if envelope.get("ok") is True and isinstance(envelope.get("result"), dict):
            return envelope["result"]
        if envelope.get("error_type") == "value_error" and isinstance(envelope.get("message"), str):
            raise ValueError(envelope["message"])
        raise StageExecutionError(stage, _stderr_tail(stderr_file))


def _file_size(handle: Any) -> int:
    try:
        return int(os.fstat(handle.fileno()).st_size)
    except OSError:
        return 0


def _stderr_tail(handle: Any) -> str:
    """Return the end of the child's stderr, for the log and the job record.

    This file was written and never read, so every stage failure collapsed into
    "stage failed" with no cause. In a closed customer network that is a support
    ticket nobody can close.
    """
    try:
        size = _file_size(handle)
        handle.seek(max(0, size - MAX_STAGE_STDERR_BYTES))
        raw = handle.read(MAX_STAGE_STDERR_BYTES)
    except OSError:
        return ""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    # Control characters would travel into the log viewer as instructions.
    cleaned = "".join(char if char.isprintable() or char in " \n\t" else " " for char in text)
    return " ".join(cleaned.split())[-MAX_STAGE_STDERR_BYTES:]


def _write_request(process: subprocess.Popen[bytes], request_bytes: bytes) -> None:
    stream = process.stdin
    if stream is None:
        return
    try:
        stream.write(request_bytes)
        stream.close()
    except (BrokenPipeError, ValueError, OSError):
        # The child exited or was killed. Its exit status is what the caller
        # reports; a failure to hand over the request adds nothing.
        return


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
