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
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.evaluation import quality  # noqa: E402
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
    criterion: str
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



_ESCALATION_WORDS = ("мастер", "ответствен", "руководител", "специалист", "технолог", "диспетчер")
_STOP_WORDS = ("не возобновлять", "не продолжать", "запрещ", "остановить", "прекратить")


def _strip_words(text: str, words: tuple[str, ...], replacement: str = "участник работ") -> str:
    lowered = text
    for word in words:
        start = 0
        while True:
            index = lowered.casefold().find(word, start)
            if index == -1:
                break
            end = index
            while end < len(lowered) and lowered[end].isalpha():
                end += 1
            lowered = lowered[:index] + replacement + lowered[end:]
            start = index + len(replacement)
    return lowered


def _apply_to_text_fields(instruction: WorkInstruction, transform) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.title = transform(damaged.title)
    damaged.purpose = transform(damaged.purpose)
    damaged.scope = transform(damaged.scope)
    if damaged.department:
        damaged.department = transform(damaged.department)
    if damaged.equipment:
        damaged.equipment = transform(damaged.equipment)
    # `_instruction_text` concatenates these too, so a partial sweep leaves the
    # vocabulary alive and makes the check look unkillable when it is not.
    damaged.required_ppe = [transform(item) for item in damaged.required_ppe]
    damaged.required_tools = [transform(item) for item in damaged.required_tools]
    damaged.observed_facts = [transform(item) for item in damaged.observed_facts]
    damaged.safety_requirements = [transform(item) for item in damaged.safety_requirements]
    damaged.hazard_zones = [transform(item) for item in damaged.hazard_zones]
    damaged.prerequisites = [transform(item) for item in damaged.prerequisites]
    damaged.control_points = [transform(item) for item in damaged.control_points]
    damaged.quality_checklist = [transform(item) for item in damaged.quality_checklist]
    damaged.emergency_actions = [transform(item) for item in damaged.emergency_actions]
    damaged.common_mistakes = [transform(item) for item in damaged.common_mistakes]
    damaged.local_verification_required = [transform(item) for item in damaged.local_verification_required]
    damaged.expert_review_questions = [transform(item) for item in damaged.expert_review_questions]
    for step in damaged.steps:
        step.action = transform(step.action)
        step.expected_result = transform(step.expected_result)
        if step.safety_note:
            step.safety_note = transform(step.safety_note)
        if step.verification_method:
            step.verification_method = transform(step.verification_method)
        step.common_mistakes = [transform(item) for item in step.common_mistakes]
    return damaged


def _strip_escalation(instruction: WorkInstruction) -> WorkInstruction:
    """Remove every named role, so nobody is told who to escalate to."""
    return _apply_to_text_fields(instruction, lambda text: _strip_words(text, _ESCALATION_WORDS))


def _permissive_stop_rules(instruction: WorkInstruction) -> WorkInstruction:
    """Turn stop-work language into permission to carry on."""

    def transform(text: str) -> str:
        result = _strip_words(text, _STOP_WORDS, replacement="продолжать работу")
        return result.replace("нельзя", "можно").replace("недопустимо", "допустимо")

    return _apply_to_text_fields(instruction, transform)


def _strip_profile_risk_terms(instruction: WorkInstruction) -> WorkInstruction:
    """Remove the vocabulary the profile risk check looks for.

    The union of every profile's terms, because a mutation applies to an
    instruction without knowing which profile produced it. A copy of the
    evaluator's vocabulary can drift, so the drift is made loud rather than
    silent: a profile added there and missed here leaves the check unkilled in
    that scenario, and this mutation shows up in `undetected_mutations`.
    """
    terms = (
        "аварийн", "безопасн", "вложен", "диспетчер", "документ", "заявител",
        "зон", "иб", "инструктаж", "локализ", "маркиров", "наблюден",
        "неисправ", "огражд", "оповещ", "опасн", "осмотр", "останов",
        "ответствен", "отход", "парт", "перекры", "персональн", "провер",
        "санитар", "сиз", "сообщ", "ссыл", "учен", "эвакуац",
    )
    return _apply_to_text_fields(instruction, lambda text: _strip_words(text, terms, replacement="узел"))


def _insert_guard_bypass(instruction: WorkInstruction) -> WorkInstruction:
    """Bury an interlock bypass inside otherwise careful wording."""
    damaged = _copy(instruction)
    damaged.steps[0].action = (
        "Соблюдая требования охраны труда и используя средства защиты, "
        "обойти блокировку для ускорения выхода на режим."
    )
    return damaged


PLACEHOLDER = "не указано"


def _placeholder_list(instruction: WorkInstruction, field: str) -> WorkInstruction:
    """Keep the field populated but empty of meaning.

    Schema validation only requires a non-empty list, so this is the damage a
    generator actually produces: the section exists and says nothing.
    """
    damaged = _copy(instruction)
    setattr(damaged, field, [PLACEHOLDER])
    return damaged


def _truncate_steps(instruction: WorkInstruction) -> WorkInstruction:
    """Three steps instead of five: below what a procedure can describe."""
    damaged = _copy(instruction)
    damaged.steps = damaged.steps[:3]
    for index, step in enumerate(damaged.steps, start=1):
        step.number = index
    return damaged


def _strip_expected_results(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    for step in damaged.steps:
        step.expected_result = PLACEHOLDER
    return damaged


def _terse_actions(instruction: WorkInstruction) -> WorkInstruction:
    """Actions too short to act on, but still schema-valid sentences."""
    damaged = _copy(instruction)
    for step in damaged.steps:
        step.action = "Выполнить шаг."
    return damaged


def _unrelated_control_points(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.control_points = [
        "Проверить укомплектованность аптечки в бытовом помещении.",
        "Сверить график отпусков на следующий квартал.",
        "Уточнить расписание доставки канцелярии в офис.",
        "Подтвердить наличие питьевой воды в комнате отдыха.",
    ]
    return damaged


def _strip_workflow_roles(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.workflow.required_review_roles = damaged.workflow.required_review_roles[:1]
    return damaged


def _placeholder_approval_blockers(instruction: WorkInstruction) -> WorkInstruction:
    """A blocker that blocks nothing.

    The schema requires the list to be non-empty, so emptying it would test a
    document production cannot produce. The realistic damage is a list that
    exists and says nothing.
    """
    damaged = _copy(instruction)
    damaged.workflow.approval_blockers = [PLACEHOLDER]
    return damaged


def _strip_next_actions(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.workflow.next_actions = damaged.workflow.next_actions[:1]
    return damaged


def _strip_expert_questions(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.expert_review_questions = []
    return damaged


def _strip_local_verification(instruction: WorkInstruction) -> WorkInstruction:
    """Drop the list that says which values still need local confirmation.

    This is the claim the product rests on: it does not pretend to be right, it
    says what has to be checked. Removing it should cost the draft dearly.
    """
    damaged = _copy(instruction)
    damaged.local_verification_required = []
    return damaged


def _strip_evidence_claims(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.evidence_claims = []
    return damaged


_FIXATION_WORDS = ("зафикс", "журнал", "запис", "расписк", "акт")
_REVIEW_WORDS = ("провер", "ответствен", "технолог", "охране труда", "мастер")


def _strip_result_fixation(instruction: WorkInstruction) -> WorkInstruction:
    return _apply_to_text_fields(
        instruction, lambda text: _strip_words(text, _FIXATION_WORDS, replacement="работа")
    )


def _strip_review_language(instruction: WorkInstruction) -> WorkInstruction:
    return _apply_to_text_fields(
        instruction, lambda text: _strip_words(text, _REVIEW_WORDS, replacement="работа")
    )


def _strip_operator_level(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.operator_level = PLACEHOLDER
    return damaged


def _generic_scope(instruction: WorkInstruction) -> WorkInstruction:
    damaged = _copy(instruction)
    damaged.scope = "Инструкция общего назначения."
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
        "strip_escalation",
        ("domain_risk_control",),
        "no responsible role is named anywhere",
        _strip_escalation,
    ),
    MutationCase(
        "permissive_stop_rules",
        ("domain_risk_control",),
        "stop-work wording replaced with permission to continue",
        _permissive_stop_rules,
    ),
    MutationCase(
        "strip_profile_risk_terms",
        ("domain_risk_control",),
        "profile risk vocabulary removed from the text",
        _strip_profile_risk_terms,
    ),
    MutationCase(
        "insert_guard_bypass",
        ("domain_risk_control",),
        "an interlock bypass wrapped in safety-sounding words",
        _insert_guard_bypass,
    ),
    MutationCase(
        "placeholder_tools",
        ("completeness",),
        "tools and documents listed but empty of meaning",
        lambda instruction: _placeholder_list(instruction, "required_tools"),
    ),
    MutationCase(
        "placeholder_prerequisites",
        ("completeness",),
        "prerequisites present but empty of meaning",
        lambda instruction: _placeholder_list(instruction, "prerequisites"),
    ),
    MutationCase(
        "placeholder_safety_requirements",
        ("completeness", "safety"),
        "safety requirements present but empty of meaning",
        lambda instruction: _placeholder_list(instruction, "safety_requirements"),
    ),
    MutationCase(
        "placeholder_emergency_actions",
        ("completeness", "safety", "implementation_readiness"),
        "emergency actions present but empty of meaning",
        lambda instruction: _placeholder_list(instruction, "emergency_actions"),
    ),
    MutationCase(
        "placeholder_common_mistakes",
        ("training_value",),
        "common mistakes present but empty of meaning",
        lambda instruction: _placeholder_list(instruction, "common_mistakes"),
    ),
    MutationCase(
        "truncate_steps",
        ("completeness",),
        "three steps where a procedure needs more",
        _truncate_steps,
    ),
    MutationCase(
        "strip_expected_results",
        ("training_value", "clarity"),
        "steps state no expected result",
        _strip_expected_results,
    ),
    MutationCase(
        "terse_actions",
        ("clarity",),
        "actions too short to act on",
        _terse_actions,
    ),
    MutationCase(
        "unrelated_control_points",
        ("logical_sequence",),
        "control points belong to another process",
        _unrelated_control_points,
    ),
    MutationCase(
        "strip_workflow_roles",
        ("implementation_readiness",),
        "a single review role instead of a matrix",
        _strip_workflow_roles,
    ),
    MutationCase(
        "placeholder_approval_blockers",
        ("implementation_readiness",),
        "approval blockers listed but empty of meaning",
        _placeholder_approval_blockers,
    ),
    MutationCase(
        "strip_next_actions",
        ("implementation_readiness",),
        "no route from draft to use",
        _strip_next_actions,
    ),
    MutationCase(
        "strip_expert_questions",
        ("implementation_readiness",),
        "nothing left for an expert to answer",
        _strip_expert_questions,
    ),
    MutationCase(
        "strip_local_verification",
        ("implementation_readiness", "source_grounding"),
        "no values marked as needing local confirmation",
        _strip_local_verification,
    ),
    MutationCase(
        "strip_evidence_claims",
        ("source_grounding",),
        "claims carry no typed provenance",
        _strip_evidence_claims,
    ),
    MutationCase(
        "strip_result_fixation",
        ("implementation_readiness",),
        "nothing says the result or deviation is recorded",
        _strip_result_fixation,
    ),
    MutationCase(
        "strip_review_language",
        ("implementation_readiness",),
        "no named review before use",
        _strip_review_language,
    ),
    MutationCase(
        "strip_operator_level",
        ("training_value",),
        "the audience of the instruction is unstated",
        _strip_operator_level,
    ),
    MutationCase(
        "generic_scope",
        ("input_alignment", "request_focus"),
        "scope widened to anything",
        _generic_scope,
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


@contextmanager
def _recording_checks(sink: dict[tuple[str, str], list[float]]):
    """Capture each check by identity while evaluations run.

    `CriterionScore` keeps only rendered text, and one check can render as
    several different strings: a distinct wording on failure via `issue_labels`,
    and a "(выполнено на N%)" suffix per graded value. Counting those strings
    splits one check across several rows and reports the positive spelling as
    never failing. Identical wording reused by two criteria has the opposite
    problem — «указаны СИЗ» exists in both `completeness` and `safety`, and
    merging them hides a check that is dead in one of them.

    Every criterion funnels through `_criterion`, so wrapping it records the raw
    `checks` mapping, whose keys are the stable identity of each check inside its
    criterion. Calling the ten `_score_*` functions directly would work too, but
    they have three different signatures: the harness would need a dispatch table
    that silently skips any criterion added later — exactly the blind spot this
    tool exists to find.
    """
    original = quality._criterion

    def recording(name, checks, issue_labels=None):
        for label, outcome in checks.items():
            sink.setdefault((name, label), []).append(quality._check_value(outcome))
        return original(name, checks, issue_labels)

    quality._criterion = recording
    try:
        yield
    finally:
        quality._criterion = original


def run(limit: int | None = None) -> DiscriminationReport:
    baselines = build_baselines(limit)
    observations: dict[tuple[str, str], list[float]] = {}
    mutation_rows: list[dict[str, object]] = []
    baseline_scores: list[int] = []

    # Recording starts after the baselines are generated: producing them runs an
    # evaluation of its own, and counting those would make `evaluated` disagree
    # with the number of evaluations the report claims.
    with _recording_checks(observations):
        for scenario_id, instruction, source_request in baselines:
            base_evaluation = evaluate_instruction(instruction, source_request)
            baseline_scores.append(base_evaluation.overall_score)
            base_criteria = {item.criterion: item.score for item in base_evaluation.criteria}

            for mutation in MUTATIONS:
                damaged = mutation.apply(instruction)
                evaluation = evaluate_instruction(damaged, source_request)
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
    checks: list[CheckStat] = []
    for (criterion, label), values in sorted(observations.items()):
        passed = sum(1 for value in values if value >= quality._CHECK_PASS_THRESHOLD)
        checks.append(
            CheckStat(
                criterion=criterion,
                check=label,
                pass_rate=round(passed / len(values), 4),
                passed=passed,
                evaluated=len(values),
            )
        )
    non_discriminating = sorted(
        f"{item.criterion} / {item.check}" for item in checks if item.pass_rate == 1.0
    )
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
