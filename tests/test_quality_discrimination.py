from app.evaluation.quality import evaluate_instruction
from app.schemas.instruction import WorkInstruction
from scripts import run_quality_discrimination as harness


def _baseline():
    return harness.build_baselines(1)[0]


def test_mutations_keep_the_instruction_schema_valid() -> None:
    _, instruction, request = _baseline()
    for mutation in harness.MUTATIONS:
        damaged, altered = mutation.damage(instruction, request)
        # A mutation that breaks the schema would be rejected before evaluation
        # in production, so it would not test anything the evaluator can meet.
        assert WorkInstruction.model_validate(damaged.model_dump()), mutation.name
        assert type(request).model_validate(altered.model_dump()), mutation.name


def test_mutations_do_not_alter_the_original_inputs() -> None:
    _, instruction, request = _baseline()
    before = instruction.model_dump()
    before_request = request.model_dump()
    for mutation in harness.MUTATIONS:
        mutation.damage(instruction, request)
    assert instruction.model_dump() == before
    assert request.model_dump() == before_request


def test_every_mutation_changes_something() -> None:
    """A case that damages neither input would be counted as a passing check."""
    _, instruction, request = _baseline()
    for mutation in harness.MUTATIONS:
        assert mutation.apply or mutation.apply_to_request, mutation.name
        damaged, altered = mutation.damage(instruction, request)
        assert (
            damaged.model_dump() != instruction.model_dump()
            or altered.model_dump() != request.model_dump()
        ), mutation.name


def test_every_mutation_declares_a_target_criterion() -> None:
    known = {
        "completeness",
        "clarity",
        "input_alignment",
        "request_focus",
        "safety",
        "logical_sequence",
        "training_value",
        "source_grounding",
        "domain_risk_control",
        "implementation_readiness",
        "executability",
        "regulatory_structure",
    }
    assert harness.MUTATIONS
    for mutation in harness.MUTATIONS:
        assert mutation.targets, mutation.name
        assert set(mutation.targets) <= known, mutation.name


def test_removing_every_safety_note_lowers_the_safety_criterion() -> None:
    _, instruction, source_request = _baseline()
    before = _criterion_score(evaluate_instruction(instruction, source_request), "safety")
    damaged = harness._strip_safety_notes(instruction)
    after = _criterion_score(evaluate_instruction(damaged, source_request), "safety")
    assert after < before


def test_report_lists_undetected_mutations_and_dead_checks() -> None:
    report = harness.run(limit=1)
    assert report.scenario_count == 1
    assert report.mutation_count == len(harness.MUTATIONS)
    assert len(report.mutations) == len(harness.MUTATIONS)
    checked = {f"{item.criterion} / {item.check}" for item in report.checks}
    assert set(report.non_discriminating_checks) <= checked
    assert report.ok is (not report.undetected_mutations)
    # A check is identified by its criterion plus its key, not by the text it
    # renders: the same wording lives in more than one criterion, and one check
    # renders differently when it fails.
    assert len(checked) == len(report.checks)
    assert {item.evaluated for item in report.checks} == {report.evaluations}


def _criterion_score(evaluation, name: str) -> int:
    return next(item.score for item in evaluation.criteria if item.criterion == name)
