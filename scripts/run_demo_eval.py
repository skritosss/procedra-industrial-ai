import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app  # noqa: E402
from app.schemas.instruction import ContextGenerationRequest, IndustryProfile  # noqa: E402


DEFAULT_SCENARIOS = PROJECT_ROOT / "examples" / "demo_scenarios.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "demo_eval_report.json"
CHECK_THRESHOLDS = {
    "minimum_steps": 5,
    "minimum_criteria": 10,
    "minimum_score": 60,
    "minimum_sources": 8,
    "external_majority": True,
}


class DemoScenario(BaseModel):
    id: str = Field(..., min_length=3, max_length=80, pattern=r"^[a-z0-9_]+$")
    title: str = Field(..., min_length=3, max_length=200)
    expected_profile: IndustryProfile
    payload: ContextGenerationRequest

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def expected_profile_matches_payload(self):
        if self.expected_profile != self.payload.industry_profile:
            raise ValueError("expected_profile must match payload.industry_profile")
        return self


def main() -> None:
    args = _parse_args()
    scenarios = _load_scenarios(args.scenarios)
    results = run_scenarios(scenarios, export_pdf=not args.skip_pdf)
    report = build_report(results)
    write_reports(report, args.output)
    print(_summary_line(report))
    if report["pass_rate"] < args.fail_under:
        raise SystemExit(1)


def run_scenarios(scenarios: list[dict[str, Any]], export_pdf: bool = True) -> list[dict[str, Any]]:
    client = TestClient(app)
    results = []
    for scenario in scenarios:
        payload = scenario["payload"]
        request = ContextGenerationRequest.model_validate(payload)
        response = client.post("/api/instructions/generate-with-context", json=request.model_dump())
        result = _base_result(scenario, response.status_code)
        if response.status_code != 200:
            result["passed"] = False
            result["issues"].append(f"generate-with-context returned {response.status_code}")
            results.append(result)
            continue

        data = response.json()
        instruction = data.get("instruction", {})
        evaluation = data.get("evaluation", {})
        sources = data.get("sources", [])
        checks = _quality_checks(scenario, data)
        result.update(
            {
                "passed": all(checks.values()),
                "checks": checks,
                "overall_score": evaluation.get("overall_score", 0),
                "risk_level": evaluation.get("risk_level"),
                "generation_mode": data.get("generation_mode"),
                "source_count": len(sources),
                "public_source_count": sum(1 for source in sources if source.get("source_type") == "public"),
                "step_count": len(instruction.get("steps", [])),
                "criterion_count": len(evaluation.get("criteria", [])),
                "instruction_title": instruction.get("title"),
                "issues": _issues_from_checks(checks),
            }
        )
        if export_pdf:
            pdf_response = client.post("/api/instructions/export-pdf", json=data)
            pdf_ok = pdf_response.status_code == 200 and pdf_response.content.startswith(b"%PDF")
            result["checks"]["pdf_export"] = pdf_ok
            result["pdf_bytes"] = len(pdf_response.content)
            if not pdf_ok:
                result["passed"] = False
                result["issues"].append(f"PDF export failed with {pdf_response.status_code}")
        results.append(result)
    return results


def build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [result["overall_score"] for result in results if isinstance(result.get("overall_score"), int)]
    public_counts = [result["public_source_count"] for result in results if isinstance(result.get("public_source_count"), int)]
    passed = [result for result in results if result.get("passed")]
    failed = [result for result in results if not result.get("passed")]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scenario_count": len(results),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "pass_rate": round(len(passed) / len(results), 3) if results else 0,
        "average_score": round(mean(scores), 2) if scores else 0,
        "average_public_sources": round(mean(public_counts), 2) if public_counts else 0,
        "check_thresholds": CHECK_THRESHOLDS,
        "risk_levels": _count_by(results, "risk_level"),
        "generation_modes": _count_by(results, "generation_mode"),
        "results": results,
        "recommendations": _recommendations(results),
    }


def write_reports(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Demo Evaluation Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Scenarios: {report['scenario_count']}",
        f"- Passed: {report['passed_count']}",
        f"- Failed: {report['failed_count']}",
        f"- Pass rate: {report['pass_rate']}",
        f"- Average score: {report['average_score']}",
        f"- Average public sources: {report['average_public_sources']}",
        f"- Check thresholds: `{json.dumps(report['check_thresholds'], ensure_ascii=False)}`",
        "",
        "## Results",
        "",
        "| Scenario | Passed | Score | Risk | Sources | Public | Steps | Issues |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for result in report["results"]:
        issues = "; ".join(result.get("issues", [])) or "-"
        lines.append(
            "| {id} | {passed} | {score} | {risk} | {sources} | {public} | {steps} | {issues} |".format(
                id=result["id"],
                passed="yes" if result.get("passed") else "no",
                score=result.get("overall_score", 0),
                risk=result.get("risk_level") or "-",
                sources=result.get("source_count", 0),
                public=result.get("public_source_count", 0),
                steps=result.get("step_count", 0),
                issues=issues.replace("|", "/"),
            )
        )
    lines.extend(["", "## Recommendations", ""])
    lines.extend(f"- {item}" for item in report["recommendations"])
    lines.append("")
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic demo evaluation scenarios.")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-pdf", action="store_true", help="Skip PDF export checks.")
    parser.add_argument("--fail-under", type=float, default=1.0, help="Exit with code 1 when pass rate is below this value.")
    return parser.parse_args()


def _load_scenarios(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Scenario file must contain a non-empty list")
    seen_ids = set()
    for scenario in data:
        parsed = DemoScenario.model_validate(scenario)
        scenario_id = parsed.id
        if not scenario_id or scenario_id in seen_ids:
            raise ValueError("Each scenario must have a unique id")
        seen_ids.add(scenario_id)
    return data


def _base_result(scenario: dict[str, Any], status_code: int) -> dict[str, Any]:
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "expected_profile": scenario["expected_profile"],
        "status_code": status_code,
        "passed": False,
        "checks": {},
        "issues": [],
    }


def _quality_checks(scenario: dict[str, Any], data: dict[str, Any]) -> dict[str, bool]:
    instruction = data.get("instruction", {})
    evaluation = data.get("evaluation", {})
    sources = data.get("sources", [])
    expected_profile = scenario["expected_profile"]
    public_sources = [source for source in sources if source.get("source_type") == "public"]
    combined_text = " ".join(
        str(value)
        for value in [
            instruction.get("title"),
            instruction.get("purpose"),
            instruction.get("scope"),
            " ".join(instruction.get("safety_requirements", [])),
            " ".join(instruction.get("control_points", [])),
        ]
    ).lower()
    return {
        "instruction_present": bool(instruction.get("title") and instruction.get("steps")),
        "minimum_steps": len(instruction.get("steps", [])) >= 5,
        "evaluation_present": bool(evaluation.get("criteria")) and len(evaluation.get("criteria", [])) >= 10,
        "score_threshold": int(evaluation.get("overall_score", 0)) >= 60,
        "sources_present": len(sources) >= 8,
        "external_majority": len(public_sources) > len(sources) / 2,
        "source_metadata": all(source.get("document_type") and source.get("contribution_reason") for source in sources),
        "expected_profile_sources": any(expected_profile in source.get("applicable_profiles", []) for source in sources)
        if expected_profile != "general"
        else True,
        "safety_content": any(term in combined_text for term in ["безопас", "риск", "опасн", "сиз", "провер"]),
        "expert_review": bool(instruction.get("expert_review_questions") or evaluation.get("expert_review_required")),
    }


def _issues_from_checks(checks: dict[str, bool]) -> list[str]:
    return [name for name, passed in checks.items() if not passed]


def _count_by(results: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        value = str(result.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _recommendations(results: list[dict[str, Any]]) -> list[str]:
    recommendations = []
    failed = [result for result in results if not result.get("passed")]
    if failed:
        recommendations.append("Review failed scenarios and tighten prompts, retrieval coverage, or deterministic fallback rules.")
    if any(result.get("public_source_count", 0) < 8 for result in results):
        recommendations.append("Increase or rebalance public-source coverage for profiles with weak external grounding.")
    if any(result.get("overall_score", 0) < 70 for result in results):
        recommendations.append("Improve instruction detail and evaluation alignment for scenarios below 70 points.")
    if not recommendations:
        recommendations.append("Demo pack is stable for portfolio and ВКР demonstrations; keep adding real enterprise cases.")
    recommendations.append("Before production use, verify current legal editions and local enterprise procedures with a domain expert.")
    return recommendations


def _summary_line(report: dict[str, Any]) -> str:
    return (
        f"Demo evaluation: {report['passed_count']}/{report['scenario_count']} passed, "
        f"average score {report['average_score']}, report written to reports/."
    )


if __name__ == "__main__":
    main()
