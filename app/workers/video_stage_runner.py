from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from app.schemas.video import VideoKeyframeResponse
from app.vision.keyframes import download_video_from_url, extract_keyframes
from app.vision.processing import add_url_processing_notes, attach_frame_analysis


MAX_STAGE_REQUEST_BYTES = 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one isolated Procedra video stage")
    parser.add_argument("stage", choices=("download", "extract", "analyze"))
    args = parser.parse_args()
    payload = _read_payload()
    try:
        result = _run_stage(args.stage, payload)
        envelope: dict[str, Any] = {"ok": True, "result": result}
    except ValueError as exc:
        envelope = {"ok": False, "error_type": "value_error", "message": str(exc)}
    except Exception:
        envelope = {"ok": False, "error_type": "stage_error"}
    sys.stdout.write(json.dumps(envelope, ensure_ascii=False))
    return 0


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_STAGE_REQUEST_BYTES + 1)
    if len(raw) > MAX_STAGE_REQUEST_BYTES:
        raise ValueError("Video stage request is too large")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Video stage request must be an object")
    return payload


def _run_stage(stage: str, payload: dict[str, Any]) -> dict[str, Any]:
    if stage == "download":
        video_id, video_path, metadata = download_video_from_url(
            str(payload["video_url"]),
            str(payload["visual_quality"]),
            organization_id=str(payload["organization_id"]),
            video_id=str(payload["video_id"]),
        )
        return {"video_id": video_id, "video_path": str(video_path.resolve()), "metadata": metadata}
    if stage == "extract":
        response = extract_keyframes(
            video_id=str(payload["video_id"]),
            video_path=Path(str(payload["video_path"])),
            original_filename=str(payload["original_filename"]),
            max_keyframes=int(payload["max_keyframes"]),
            source_url=str(payload["source_url"]) if payload.get("source_url") else None,
            extracted_context=str(payload.get("extracted_context") or ""),
            transcript=str(payload.get("transcript") or ""),
            visual_quality=str(payload.get("visual_quality") or "local"),
            organization_id=str(payload["organization_id"]),
        )
        return response.model_dump(mode="json")
    if stage == "analyze":
        response = VideoKeyframeResponse.model_validate(payload["response"])
        attach_frame_analysis(response)
        if payload.get("source_kind") == "url":
            add_url_processing_notes(response)
        return response.model_dump(mode="json")
    raise ValueError("Unsupported video stage")


if __name__ == "__main__":
    raise SystemExit(main())
