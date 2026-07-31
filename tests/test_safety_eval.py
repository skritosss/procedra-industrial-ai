import json
import subprocess
import sys
from pathlib import Path

from scripts.run_safety_eval import DEFAULT_CORPUS, evaluate_corpus


def test_adversarial_corpus_has_ru_en_hostile_and_benign_coverage() -> None:
    cases = json.loads(DEFAULT_CORPUS.read_text(encoding="utf-8"))

    assert len(cases) >= 20
    assert {case["language"] for case in cases} == {"ru", "en"}
    assert any(case["expected_codes"] for case in cases)
    assert any(not case["expected_codes"] for case in cases)
    assert {code for case in cases for code in case["expected_codes"]} == {
        "hazardous_action",
        "contradictory_context",
        "unsupported_numeric_claim",
        "instruction_override",
    }


def test_adversarial_corpus_reports_zero_known_false_results() -> None:
    report = evaluate_corpus()

    assert report["passed_case_count"] == report["case_count"]
    assert report["false_positive_labels"] == 0
    assert report["false_negative_labels"] == 0
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0


def test_safety_eval_cli_writes_reproducible_report(tmp_path: Path) -> None:
    output = tmp_path / "safety-report.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_safety_eval.py",
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "SAFETY_EVAL passed=" in completed.stdout
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["failed_case_ids"] == []
