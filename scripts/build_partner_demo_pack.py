from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "partner_demo_pack"
BRAND_ASSET_DIR = PROJECT_ROOT / "app" / "static" / "assets" / "brand"
DEMO_REQUEST = {
    "task": "Составить инструкцию по безопасной подготовке ленточнопильного станка к запуску",
    "user_level": "new_operator",
    "instruction_type": "equipment_startup",
    "industry_profile": "manufacturing",
    "department": "Заготовительный участок",
    "equipment": "Ленточнопильный станок",
    "operation_name": "Подготовка станка к запуску",
    "technical_context": (
        "Перед запуском проверить ограждения, аварийную остановку, натяжение полотна, "
        "отсутствие посторонних предметов и состояние зоны резания. Точные параметры "
        "станка подтверждаются по паспорту оборудования и локальной карте операции."
    ),
    "max_sources": 15,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an isolated, reproducible industrial partner demo pack.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    manifest = build_partner_demo_pack(args.output_dir)
    print(
        "PARTNER_DEMO_PACK_OK "
        f"score={manifest['instruction']['overall_score']} "
        f"sources={manifest['instruction']['source_count']} "
        f"artifacts={len(manifest['artifacts'])}"
    )


def build_partner_demo_pack(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    _remove_previous_generated_files(output_dir)

    with tempfile.TemporaryDirectory(prefix="industrial-ai-partner-demo-") as temporary:
        temp_root = Path(temporary)
        _configure_isolated_environment(temp_root)

        from fastapi.testclient import TestClient

        from app.core.settings import get_settings
        from app.main import app
        from app.api import instructions as instruction_api
        from app.vision import keyframes as keyframe_storage
        import app.main as main_module

        get_settings.cache_clear()
        keyframe_storage.PROJECT_ROOT = temp_root
        keyframe_storage.UPLOAD_DIR = temp_root / "uploads" / "videos"
        keyframe_storage.KEYFRAME_DIR = temp_root / "generated" / "keyframes"
        instruction_api.keyframe_storage.PROJECT_ROOT = temp_root
        main_module.KEYFRAMES_DIR = keyframe_storage.KEYFRAME_DIR

        client = TestClient(app)
        auth = _expect_json(
            client.post(
                "/api/auth/register",
                json={
                    "email": "partner-demo@example.invalid",
                    "full_name": "Алексей Технолог",
                    "password": "PartnerDemo-Only-2026!",
                    "role": "technologist",
                    "organization_name": "Демонстрационный производственный участок",
                },
            ),
            200,
            "demo registration",
        )
        token = auth.get("access_token")
        if not token:
            raise RuntimeError("Demo registration did not return an API session")
        headers = {"Authorization": f"Bearer {token}"}

        instruction = _expect_json(
            client.post("/api/instructions/generate-with-context", json=DEMO_REQUEST, headers=headers),
            200,
            "instruction generation",
        )
        history = _expect_json(
            client.post("/api/instructions/history", json={"payload": instruction}, headers=headers),
            200,
            "history save",
        )["record"]
        instruction_id = history["instruction_id"]
        version = history["version"]
        workflow_url = f"/api/instructions/history/{instruction_id}/versions/{version}/workflow"
        review = _expect_json(
            client.patch(
                workflow_url,
                headers=headers,
                json={
                    "status": "expert_review",
                    "reviewer": "Алексей Технолог",
                    "reviewer_role": "technologist",
                    "comment": "Проверить локальные допуски и паспорт конкретной модели перед внедрением.",
                    "resolved_blockers": [],
                },
            ),
            200,
            "expert-review transition",
        )["record"]
        approval_blockers = instruction["instruction"]["workflow"].get("approval_blockers", [])
        approved = _expect_json(
            client.patch(
                workflow_url,
                headers=headers,
                json={
                    "status": "approved",
                    "reviewer": "Алексей Технолог",
                    "reviewer_role": "technologist",
                    "comment": "Демонстрационное утверждение после проверки структуры и контрольных точек.",
                    "resolved_blockers": approval_blockers,
                },
            ),
            200,
            "approval transition",
        )["record"]

        execution_steps = [
            {"label": f"{step['number']}. {step['action']}", "completed": True}
            for step in instruction["instruction"]["steps"]
        ]
        execution_quality = [
            {"label": item, "completed": True}
            for item in instruction["instruction"]["control_points"][:3]
        ]
        execution = _expect_json(
            client.post(
                f"/api/instructions/history/{instruction_id}/versions/{version}/execution",
                headers=headers,
                json={
                    "executor": "Оператор демонстрационной смены",
                    "notes": "Пробный проход выполнен без реального запуска оборудования.",
                    "steps": execution_steps,
                    "quality_items": execution_quality,
                },
            ),
            200,
            "execution evidence",
        )
        audit = _expect_json(
            client.get(
                f"/api/instructions/history/{instruction_id}/versions/{version}/audit",
                headers=headers,
            ),
            200,
            "audit trail",
        )
        pdf_response = client.post("/api/instructions/export-pdf", json=instruction, headers=headers)
        if pdf_response.status_code != 200 or not pdf_response.content.startswith(b"%PDF"):
            raise RuntimeError(f"PDF export failed with status {pdf_response.status_code}")

        video_path = temp_root / "partner-demo-machine-check.mp4"
        _build_synthetic_video(video_path)
        with video_path.open("rb") as video_file:
            video = _expect_json(
                client.post(
                    "/api/videos/keyframes",
                    headers=headers,
                    data={"max_keyframes": "4"},
                    files={"file": (video_path.name, video_file, "video/mp4")},
                ),
                200,
                "video keyframe extraction",
            )
        video_request = {
            **DEMO_REQUEST,
            "technical_context": video["extracted_context"],
            "keyframes": video["keyframes"],
            "frame_analyses": video["frame_analyses"],
            "video_segments": video["video_segments"],
        }
        video_instruction = _expect_json(
            client.post("/api/instructions/generate-from-video", json=video_request, headers=headers),
            200,
            "video instruction generation",
        )

        _write_json(output_dir / "01-request.json", DEMO_REQUEST)
        _write_json(output_dir / "02-instruction.json", instruction)
        (output_dir / "03-instruction.md").write_text(instruction["markdown"], encoding="utf-8")
        (output_dir / "04-instruction.pdf").write_bytes(pdf_response.content)
        _write_json(
            output_dir / "05-lifecycle.json",
            {"saved": history, "expert_review": review, "approved": approved},
        )
        _write_json(output_dir / "06-execution.json", execution)
        _write_json(output_dir / "07-audit.json", audit)
        shutil.copy2(video_path, output_dir / "08-fallback-demo-video.mp4")
        _write_json(output_dir / "09-video-keyframes.json", video)
        _write_json(output_dir / "10-video-instruction.json", video_instruction)
        frame_output = output_dir / "keyframes"
        frame_output.mkdir(exist_ok=True)
        for frame in video["keyframes"]:
            source = temp_root / frame["image_path"]
            shutil.copy2(source, frame_output / source.name)
        brand_output = output_dir / "brand"
        brand_output.mkdir(exist_ok=True)
        for filename in (
            "procedra-wordmark.svg",
            "procedra-wordmark.png",
            "procedra-wordmark-monochrome.svg",
            "procedra-wordmark-reversed.svg",
            "procedra-favicon.svg",
        ):
            shutil.copy2(BRAND_ASSET_DIR / filename, brand_output / filename)

    manifest = _build_manifest(output_dir, instruction, approved, execution, audit, video)
    _write_json(output_dir / "manifest.json", manifest)
    (output_dir / "talk-track.md").write_text(_render_talk_track(manifest), encoding="utf-8")
    return manifest


def _configure_isolated_environment(temp_root: Path) -> None:
    os.environ.update(
        {
            "DEPLOYMENT_MODE": "demo",
            "OPENAI_ENABLED": "false",
            "DATABASE_PATH": str(temp_root / "generated" / "app.sqlite3"),
            "METRICS_DATABASE_PATH": str(temp_root / "generated" / "metrics.sqlite3"),
            "RATE_LIMIT_ENABLED": "false",
            "API_ACCESS_TOKEN": "",
        }
    )


def _expect_json(response: Any, expected_status: int, stage: str) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise RuntimeError(f"{stage} failed with {response.status_code}: {response.text[:500]}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{stage} returned a non-object payload")
    return payload


def _build_synthetic_video(path: Path) -> None:
    width, height, fps = 640, 360, 10
    fourcc = getattr(cv2, "VideoWriter_fourcc")(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not create the fallback demo video")
    scenes = [
        ("1. Inspect work zone", (38, 86, 128), (130, 250, 90, 250)),
        ("2. Check guard and E-stop", (48, 118, 76), (210, 110, 300, 220)),
        ("3. Record readiness", (104, 68, 132), (360, 220, 180, 80)),
    ]
    try:
        for title, background, rectangle in scenes:
            for frame_number in range(fps * 2):
                frame = np.full((height, width, 3), background, dtype=np.uint8)
                x, y, rect_width, rect_height = rectangle
                cv2.rectangle(frame, (x, y), (x + rect_width, y + rect_height), (230, 230, 225), 3)
                cv2.circle(frame, (80 + frame_number * 12, 300), 24, (50, 180, 240), -1)
                cv2.putText(frame, title, (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.putText(
                    frame,
                    "TECHNICAL FALLBACK FIXTURE - NOT A REAL MACHINE",
                    (30, 340),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (255, 255, 255),
                    1,
                )
                writer.write(frame)
    finally:
        writer.release()
    if not path.is_file() or path.stat().st_size < 1_000:
        raise RuntimeError("Fallback demo video was not created")


def _build_manifest(
    output_dir: Path,
    instruction: dict[str, Any],
    approved: dict[str, Any],
    execution: dict[str, Any],
    audit: dict[str, Any],
    video: dict[str, Any],
) -> dict[str, Any]:
    artifacts = []
    for path in sorted(item for item in output_dir.rglob("*") if item.is_file()):
        artifacts.append(
            {
                "path": str(path.relative_to(output_dir)),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "purpose": "Controlled local industrial-partner demonstration",
        "data_classification": "Synthetic demonstration data; no partner or production data",
        "instruction": {
            "title": instruction["instruction"]["title"],
            "overall_score": instruction["evaluation"]["overall_score"],
            "risk_level": instruction["evaluation"]["risk_level"],
            "source_count": len(instruction["sources"]),
            "public_source_count": sum(
                1 for source in instruction["sources"] if source.get("source_type") == "public"
            ),
            "step_count": len(instruction["instruction"]["steps"]),
            "generation_mode": instruction["generation_mode"],
        },
        "workflow": {
            "final_status": approved["workflow_status"],
            "audit_event_count": len(audit["events"]),
            "execution_completed_steps": execution["record"]["completed_steps"],
            "execution_total_steps": execution["record"]["total_steps"],
        },
        "video": {
            "fixture_kind": "synthetic technical fallback",
            "keyframe_count": len(video["keyframes"]),
            "segment_count": len(video["video_segments"]),
            "frame_analysis_modes": sorted(
                {analysis["analysis_mode"] for analysis in video["frame_analyses"]}
            ),
        },
        "artifacts": artifacts,
    }


def _render_talk_track(manifest: dict[str, Any]) -> str:
    instruction = manifest["instruction"]
    workflow = manifest["workflow"]
    video = manifest["video"]
    return f"""# Partner demo talk track

## Positioning

Procedra turns an operator task and approved technical context
into a review-ready instruction draft. It does not replace the technologist,
safety specialist, local procedure, or equipment passport.

## Seven-minute flow

1. **Problem (30 sec):** instruction preparation is manual, inconsistent, and
   difficult to trace from source to review and trial execution.
2. **Input (45 sec):** load `01-request.json`; point out the operation, equipment,
   worker level, local context, and explicit requirement to verify exact settings.
3. **Generation (90 sec):** show `{instruction['title']}`, its
   {instruction['step_count']} steps, safety requirements, control points, and
   expert-review questions.
4. **Evidence (60 sec):** show {instruction['source_count']} sources, including
   {instruction['public_source_count']} public references. Explain that edition
   and local applicability still require expert confirmation.
5. **Quality and editability (45 sec):** show deterministic score
   {instruction['overall_score']}/100, risk `{instruction['risk_level']}`, Markdown,
   JSON, and the exported PDF.
6. **Governance (75 sec):** show draft → expert review → `{workflow['final_status']}`,
   {workflow['audit_event_count']} audit events, and trial execution evidence
   {workflow['execution_completed_steps']}/{workflow['execution_total_steps']} steps.
7. **Video (45 sec):** show {video['keyframe_count']} fallback-fixture keyframes and
   {video['segment_count']} semantic stages. State clearly that the included video
   is synthetic and only proves flow reliability; replace it with an approved
   partner clip for the meeting.
8. **Pilot question (45 sec):** ask for one instruction type, one approved document
   set, the mandatory template fields, reviewers, and a success metric.

## Do not improvise

- Do not claim legal approval, autonomous publishing, or exact machine settings.
- Do not upload partner-confidential data during the first demonstration.
- Do not depend on a public video URL or live OpenAI call for the core flow.
- If the live UI fails, show `03-instruction.md`, `04-instruction.pdf`, lifecycle,
  audit, and video artifacts from this pack.

## Proposed pilot

Two to four weeks, one instruction family, a small approved document set, named
reviewers, and baseline/target measurements for preparation time, completeness,
review iterations, and traceability.
"""


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_previous_generated_files(output_dir: Path) -> None:
    for path in output_dir.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


if __name__ == "__main__":
    main()
