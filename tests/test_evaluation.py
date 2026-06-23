from app.evaluation.quality import evaluate_instruction
from app.generation.fallback import generate_fallback_instruction
from app.schemas.instruction import InstructionRequest


def test_evaluate_fallback_instruction_returns_scores() -> None:
    request = InstructionRequest(
        task="Подготовить рабочее место оператора перед запуском оборудования",
        instruction_type="workplace_preparation",
        department="Кузнечно-прессовый участок",
        equipment="Рабочее место оператора",
        technical_context="Проверить ограждения, аварийную кнопку и отсутствие посторонних предметов.",
    )
    instruction = generate_fallback_instruction(request)

    evaluation = evaluate_instruction(instruction, request)

    assert evaluation.overall_score >= 75
    assert len(evaluation.criteria) == 10
    assert evaluation.verdict
    assert evaluation.recommendations
    assert evaluation.risk_level in {"low", "medium", "high", "critical"}
    assert evaluation.expert_review_required is True
    assert evaluation.expert_review_notes


def test_evaluation_detects_input_alignment() -> None:
    request = InstructionRequest(
        task="Проверить оборудование перед запуском",
        department="Испытательный участок",
        equipment="Вибростенд",
        technical_context="Проверить защитный кожух и аварийную остановку.",
    )
    instruction = generate_fallback_instruction(request)

    evaluation = evaluate_instruction(instruction, request)
    input_alignment = next(item for item in evaluation.criteria if item.criterion == "input_alignment")
    request_focus = next(item for item in evaluation.criteria if item.criterion == "request_focus")
    source_grounding = next(item for item in evaluation.criteria if item.criterion == "source_grounding")
    domain_risk_control = next(item for item in evaluation.criteria if item.criterion == "domain_risk_control")

    assert input_alignment.score >= 75
    assert request_focus.score >= 60
    assert source_grounding.score >= 50
    assert domain_risk_control.score >= 50
