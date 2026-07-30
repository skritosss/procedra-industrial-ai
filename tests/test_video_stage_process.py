from __future__ import annotations

import io

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
