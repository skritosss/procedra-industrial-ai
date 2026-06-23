import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.instruction import ContextGenerationRequest
from scripts.run_demo_eval import DemoScenario, build_report, run_scenarios, write_reports


SCENARIO_PATH = Path("examples/demo_scenarios.json")
VIDEO_SCENARIO_PATH = Path("examples/video_demo_scenarios.json")


def _scenarios() -> list[dict]:
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


def test_demo_scenarios_are_valid_and_broad() -> None:
    scenarios = _scenarios()
    ids = [scenario["id"] for scenario in scenarios]
    profiles = {scenario["expected_profile"] for scenario in scenarios}

    assert len(scenarios) == 15
    assert len(ids) == len(set(ids))
    assert {
        "manufacturing",
        "construction",
        "occupational_safety",
        "emergency_response",
        "public_service",
        "housing_utilities",
        "healthcare",
        "education",
        "food_production",
        "transport",
        "information_security",
        "general",
    }.issubset(profiles)
    for scenario in scenarios:
        request = ContextGenerationRequest.model_validate(scenario["payload"])
        assert request.max_sources == 15


def test_demo_eval_runner_generates_passing_report_without_pdf(tmp_path) -> None:
    scenarios = _scenarios()[:3]

    results = run_scenarios(scenarios, export_pdf=False)
    report = build_report(results)
    output = tmp_path / "demo_eval_report.json"
    write_reports(report, output)

    assert report["scenario_count"] == 3
    assert report["passed_count"] == 3
    assert report["failed_count"] == 0
    assert report["average_score"] >= 60
    assert output.exists()
    assert output.with_suffix(".md").exists()
    assert "Demo Evaluation Report" in output.with_suffix(".md").read_text(encoding="utf-8")
    assert all(result["source_count"] >= 8 for result in report["results"])
    assert all(result["public_source_count"] > result["source_count"] / 2 for result in report["results"])
    assert report["check_thresholds"]["minimum_steps"] == 5
    assert report["check_thresholds"]["minimum_sources"] == 8


def test_demo_scenario_metadata_must_match_payload_profile() -> None:
    scenario = _scenarios()[0] | {"expected_profile": "construction"}

    with pytest.raises(ValidationError):
        DemoScenario.model_validate(scenario)


def test_demo_eval_runner_full_pack_without_pdf() -> None:
    results = run_scenarios(_scenarios(), export_pdf=False)
    report = build_report(results)

    assert report["scenario_count"] == 15
    assert report["passed_count"] == 15
    assert report["pass_rate"] == 1.0


def test_video_demo_scenarios_are_valid_manual_test_manifest() -> None:
    scenarios = json.loads(VIDEO_SCENARIO_PATH.read_text(encoding="utf-8"))
    ids = [scenario["id"] for scenario in scenarios]

    assert len(scenarios) >= 5
    assert len(ids) == len(set(ids))
    for scenario in scenarios:
        assert scenario["title"]
        assert scenario["industry_profile"]
        assert scenario["instruction_type"]
        assert scenario["search_hint"].startswith("YouTube:")
        assert scenario["expected_visual_signals"]
        assert scenario["expected_text_signals"]
        assert "url" in scenario
