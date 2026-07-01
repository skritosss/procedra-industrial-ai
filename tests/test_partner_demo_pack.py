import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_partner_demo_pack_builds_complete_isolated_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "partner-demo-pack"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_partner_demo_pack.py",
            "--output-dir",
            str(output_dir),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "PARTNER_DEMO_PACK_OK" in result.stdout
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_classification"].startswith("Synthetic")
    assert manifest["instruction"]["overall_score"] >= 80
    assert manifest["instruction"]["source_count"] == 15
    assert manifest["workflow"]["final_status"] == "approved"
    assert manifest["workflow"]["execution_completed_steps"] == manifest["workflow"]["execution_total_steps"]
    assert manifest["workflow"]["audit_event_count"] == 4
    assert manifest["video"]["keyframe_count"] >= 3
    assert manifest["video"]["segment_count"] >= 1
    assert (output_dir / "04-instruction.pdf").read_bytes().startswith(b"%PDF")
    summary = (output_dir / "pilot-summary.md").read_text(encoding="utf-8")
    assert "What was tested" in summary
    assert "What was not tested" in summary
    assert "not customer validation" in summary
    assert (output_dir / "08-fallback-demo-video.mp4").stat().st_size > 1_000
    assert list((output_dir / "keyframes").glob("frame_*.jpg"))
    assert (output_dir / "brand" / "procedra-wordmark.svg").is_file()
    assert (output_dir / "brand" / "procedra-wordmark.png").is_file()
    assert any(item["path"] == "pilot-summary.md" for item in manifest["artifacts"])
    assert any(item["path"] == "brand/procedra-wordmark.svg" for item in manifest["artifacts"])
