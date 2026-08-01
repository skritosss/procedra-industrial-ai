"""Measure whether the quality criteria can tell a good draft from a bad one.

The evaluation criteria are built from checks over a generated instruction. A
check that passes for every document carries no information, however sensible
its wording is. This script quantifies that: it generates baseline instructions
from the demo scenarios, damages each one in a controlled way, and reports how
every check and every criterion responds.

Mutations deliberately stay inside the schema. A real model does not return an
instruction with an empty PPE list — that is rejected before evaluation. It
returns an instruction whose PPE list says "не указано", whose steps all expect
"выполнено", or whose text is padded with the words the checks look for. Those
are the documents the criteria have to catch.

Exit code is 1 when a mutation fails to lower the criterion it targets, so the
set of discriminating checks can only grow.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.evaluation.quality import evaluate_instruction  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.instruction import (  # noqa: E402
    ContextGenerationRequest,
    InstructionRequest,
    WorkInstruction,
)

DEFAULT_SCENARIOS = PROJECT_ROOT / "examples" / "demo_scenarios.json"
DEFAULT_REPORT = PROJECT_ROOT / "reports" / "quality_discrimination_report.json"

Mutation = Callable[[WorkInstruction], WorkInstruction]

_STUFFING = (
    "безопасность проверка ответственный мастер технолог ограждение аварийный "
    "останов контроль журнал фиксация подтвердить локально документация участок "
    "опасная зона средства защиты не продолжать запрещается"
)


@dataclass(frozen=True)
class CheckStat:
    check: str
    pass_rate: float
    passed: int
    evaluated: int


@dataclass(frozen=True)
class DiscriminationReport:
    scenario_count: int
    mutation_count: int
    evaluations: int
    baseline_scores: list[int]
    baseline_distinct_scores: list[int]
    undetected_mutations: list[str]
    non_discriminating_checks: list[str]
    check_count: int
    checks: list[CheckStat]
    mutations: list[dict[str, object]]
    ok: bool


@dataclass(frozen=True)
class MutationCase:
    name: str
    targets: tuple[str, ...]
    describe: str
    apply: Mutation


def _copy(instruction: WorkInstruction) -> WorkInstruction:
    return instruction.model_copy(deep=True)


def _placeholder_ppe(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.required_ppe = ["не указано"]
    return damaged


def _placeholder_hazard_zones(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.hazard_zones = ["—"]
    return damaged


def _vacuous_expected_results(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    for step in damaged.steps:
        step.expected_result = "Выполнено"
    return damaged


def _vague_actions(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    for step in damaged.steps:
        step.action = "Выполнить необходимые действия по операции при необходимости"
    return damaged


def _duplicate_steps(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    first = damaged.steps[0]
    for index, step in enumerate(damaged.steps, start=1):
        step.action = first.action
        step.expected_result = first.expected_result
        step.safety_note = first.safety_note
        step.verification_method = first.verification_method
        step.number = index
    return damaged


def _reversed_step_order(instruction: WorkInstruction) -> WorkInstruction:
    """Reverse the work while keeping numbering sequential.

    The schema already rejects non-sequential `number` values, so renumbering
    would test a path production can never reach. Reversing the content instead
    produces a document that validates cleanly and is still nonsense: the final
    check comes first and the preparation comes last.
    """
    damaged = _copy(instruction)
    payloads = [
        (step.action, step.expected_result, step.safety_note, step.verification_method)
        for step in damaged.steps
    ]
    for step, payload in zip(damaged.steps, reversed(payloads)):
        step.action, step.expected_result, step.safety_note, step.verification_method = payload
    return damaged


def _keyword_stuffing(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.purpose = _STUFFING
    damaged.scope = _STUFFING
    damaged.quality_checklist = [_STUFFING]
    for step in damaged.steps:
        step.action = _STUFFING
        step.expected_result = _STUFFING
        step.safety_note = _STUFFING
        step.verification_method = _STUFFING
    return damaged


def _off_topic_steps(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    replacements = [
        "Отсортировать входящую корреспонденцию по датам поступления",
        "Внести реквизиты контрагента в журнал регистрации договоров",
        "Согласовать график отпусков с отделом кадров",
        "Проверить наличие канцелярских принадлежностей на складе",
        "Обновить контактные данные в адресной книге",
    ]
    for index, step in enumerate(damaged.steps):
        step.action = replacements[index % len(replacements)]
        step.expected_result = "Запись внесена в журнал"
    return damaged


def _unsupported_numbers(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    values = ["затянуть до 45 нм", "нагреть до 180 °c", "выдержать 30 мин", "давление 12 бар"]
    for index, step in enumerate(damaged.steps):
        step.action = f"{step.action}; {values[index % len(values)]}"
    return damaged


def _internal_contradiction(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.steps[0].action = "Снять защитное ограждение для доступа к зоне резания"
    if len(damaged.steps) > 1:
        damaged.steps[-1].action = "Убедиться, что защитное ограждение закрыто и не снималось"
    return damaged


def _strip_verification(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    for step in damaged.steps:
        step.verification_method = None
    return damaged


def _strip_safety_notes(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    for step in damaged.steps:
        step.safety_note = None
    return damaged


def _confirm_unverified_claims(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    for claim in damaged.evidence_claims:
        claim.text = f"Подтвержденное требование: {claim.text}"
    return damaged


def _placeholder_control_points(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.control_points = ["контроль", "контроль", "контроль", "контроль"]
    return damaged


MUTATIONS: tuple[MutationCase, ...] = (
    MutationCase(
        "placeholder_ppe",
        ("completeness", "safety"),
        "PPE list present but says «не указано»",
        _placeholder_ppe,
    ),
    MutationCase(
        "placeholder_hazard_zones",
        ("completeness", "safety"),
        "hazard zones present but say «—»",
        _placeholder_hazard_zones,
    ),
    MutationCase(
        "vacuous_expected_results",
        ("clarity", "training_value"),
        "every step expects «Выполнено»",
        _vacuous_expected_results,
    ),
    MutationCase(
        "vague_actions",
        ("clarity",),
        "every action is a filler phrase",
        _vague_actions,
    ),
    MutationCase(
        "duplicate_steps",
        ("clarity", "logical_sequence"),
        "all steps repeat the first one",
        _duplicate_steps,
    ),
    MutationCase(
        "reversed_step_order",
        ("logical_sequence",),
        "the work runs backwards under sequential numbering",
        _reversed_step_order,
    ),
    MutationCase(
        "keyword_stuffing",
        ("clarity", "request_focus"),
        "content replaced with the words the checks look for",
        _keyword_stuffing,
    ),
    MutationCase(
        "off_topic_steps",
        ("request_focus", "input_alignment"),
        "steps describe an unrelated office procedure",
        _off_topic_steps,
    ),
    MutationCase(
        "unsupported_numbers",
        ("source_grounding",),
        "precise values injected without any verification marker",
        _unsupported_numbers,
    ),
    MutationCase(
        "internal_contradiction",
        ("safety", "logical_sequence"),
        "one step removes the guard, another asserts it was never removed",
        _internal_contradiction,
    ),
    MutationCase(
        "strip_verification",
        ("clarity", "training_value"),
        "no step has a verification method",
        _strip_verification,
    ),
    MutationCase(
        "strip_safety_notes",
        ("safety",),
        "no step has a safety note",
        _strip_safety_notes,
    ),
    MutationCase(
        "confirm_unverified_claims",
        ("source_grounding",),
        "unverified claims relabelled as confirmed",
        _confirm_unverified_claims,
    ),
    MutationCase(
        "placeholder_control_points",
        ("completeness", "implementation_readiness"),
        "control points present but empty of meaning",
        _placeholder_control_points,
    ),
)


def build_baselines(limit: int | None) -> list[tuple[str, WorkInstruction, InstructionRequest]]:
    scenarios = json.loads(DEFAULT_SCENARIOS.read_text(encoding="utf-8"))
    if limit:
        scenarios = scenarios[:limit]
    client = TestClient(app)
    baselines = []
    for scenario in scenarios:
        payload = ContextGenerationRequest.model_validate(scenario["payload"])
        response = client.post(
            "/api/instructions/generate-with-context",
            json=payload.model_dump(),
        )
        response.raise_for_status()
        instruction = WorkInstruction.model_validate(response.json()["instruction"])
        source_request = InstructionRequest.model_validate(scenario["payload"])
        baselines.append((scenario["id"], instruction, source_request))
    return baselines


def run(limit: int | None = None) -> DiscriminationReport:
    baselines = build_baselines(limit)
    check_pass: Counter[str] = Counter()
    check_total: Counter[str] = Counter()
    mutation_rows: list[dict[str, object]] = []
    baseline_scores: list[int] = []

    for scenario_id, instruction, source_request in baselines:
        base_evaluation = evaluate_instruction(instruction, source_request)
        baseline_scores.append(base_evaluation.overall_score)
        base_criteria = {item.criterion: item.score for item in base_evaluation.criteria}
        _tally(base_evaluation, check_pass, check_total)

        for mutation in MUTATIONS:
            damaged = mutation.apply(instruction)
            evaluation = evaluate_instruction(damaged, source_request)
            _tally(evaluation, check_pass, check_total)
            criteria = {item.criterion: item.score for item in evaluation.criteria}
            dropped = sorted(
                name for name, score in criteria.items() if score < base_criteria[name]
            )
            detected = [target for target in mutation.targets if target in dropped]
            mutation_rows.append(
                {
                    "scenario": scenario_id,
                    "mutation": mutation.name,
                    "describes": mutation.describe,
                    "targets": list(mutation.targets),
                    "overall_before": base_evaluation.overall_score,
                    "overall_after": evaluation.overall_score,
                    "criteria_dropped": dropped,
                    "targets_detected": detected,
                    "undetected": not detected,
                }
            )

    undetected = sorted({str(row["mutation"]) for row in mutation_rows if row["undetected"]})
    checks: list[CheckStat] = [
        CheckStat(
            check=label,
            pass_rate=round(check_pass[label] / total, 4),
            passed=check_pass[label],
            evaluated=total,
        )
        for label, total in sorted(check_total.items())
    ]
    non_discriminating = sorted(item.check for item in checks if item.pass_rate == 1.0)
    return DiscriminationReport(
        scenario_count=len(baselines),
        mutation_count=len(MUTATIONS),
        evaluations=len(baselines) * (len(MUTATIONS) + 1),
        baseline_scores=baseline_scores,
        baseline_distinct_scores=sorted(set(baseline_scores)),
        undetected_mutations=undetected,
        non_discriminating_checks=non_discriminating,
        check_count=len(checks),
        checks=checks,
        mutations=mutation_rows,
        ok=not undetected,
    )


def _tally(evaluation, check_pass: Counter[str], check_total: Counter[str]) -> None:
    for criterion in evaluation.criteria:
        for label in criterion.strengths:
            check_pass[label] += 1
            check_total[label] += 1
        for label in criterion.issues:
            check_total[label] += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N scenarios.")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--quiet", action="store_true", help="Print the summary line only.")
    args = parser.parse_args()

    report = run(args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if not args.quiet:
        print("\nUndetected mutations (damage the evaluator does not see):")
        for name in report.undetected_mutations or ["— none —"]:
            print(f"  {name}")
        print(
            f"\nNon-discriminating checks: "
            f"{len(report.non_discriminating_checks)}/{report.check_count} always pass"
        )

    print(
        "QUALITY_DISCRIMINATION "
        f"scenarios={report.scenario_count} mutations={report.mutation_count} "
        f"undetected={len(report.undetected_mutations)} "
        f"always_pass={len(report.non_discriminating_checks)}/{report.check_count} "
        f"baseline_scores={report.baseline_distinct_scores}"
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
