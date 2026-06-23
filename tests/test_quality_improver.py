from types import SimpleNamespace

from app.evaluation.quality import evaluate_instruction
from app.generation import pipeline
from app.generation.quality_improver import improve_instruction_quality
from app.schemas.instruction import InstructionRequest, InstructionStep, WorkInstruction


def _sparse_instruction() -> WorkInstruction:
    return WorkInstruction(
        title="Инструкция по проверке оборудования",
        purpose="Выполнить проверку оборудования.",
        scope="Проверка оборудования на участке.",
        department=None,
        equipment=None,
        operator_level="Новый оператор",
        required_ppe=["Спецодежда"],
        required_tools=["Чеклист"],
        safety_requirements=["Проверить рабочее место."],
        hazard_zones=["Рабочая зона"],
        prerequisites=["Получить задание."],
        steps=[
            InstructionStep(
                number=1,
                action="Проверить оборудование перед работой",
                expected_result="Оборудование проверено",
            )
        ],
        control_points=["Проверка выполнена."],
        quality_checklist=["Результат проверен."],
        emergency_actions=["Сообщить ответственному."],
        common_mistakes=["Проверка по памяти."],
        observed_facts=[],
        local_verification_required=[],
        expert_review_questions=[],
    )


def test_quality_improver_adds_safety_grounding_and_readiness_items() -> None:
    request = InstructionRequest(
        task="Проверить строительную площадку перед началом работ",
        industry_profile="construction",
        instruction_type="inspection",
        department="Строительный участок",
        technical_context="Перед началом работ проверить ограждение зоны, СИЗ и отсутствие посторонних лиц.",
    )

    improved = improve_instruction_quality(_sparse_instruction(), request)
    evaluation = evaluate_instruction(improved, request)

    assert improved.steps[0].safety_note
    assert improved.steps[0].verification_method
    assert len(improved.safety_requirements) >= 4
    assert len(improved.control_points) >= 4
    assert len(improved.quality_checklist) >= 4
    assert len(improved.emergency_actions) >= 4
    assert len(improved.local_verification_required) >= 3
    assert len(improved.expert_review_questions) >= 3
    assert any("Строительство" in item for item in improved.observed_facts)
    assert evaluation.overall_score >= 70


def test_pipeline_improves_valid_openai_instruction_before_response(monkeypatch) -> None:
    request = InstructionRequest(
        task="Проверить оборудование перед запуском после приемки смены",
        instruction_type="equipment_startup",
        industry_profile="manufacturing",
        equipment="Ленточнопильный станок",
    )
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(openai_enabled=True, openai_api_key="present", openai_model="test-model", openai_timeout_seconds=1),
    )
    monkeypatch.setattr(pipeline, "_generate_with_openai", lambda **kwargs: _sparse_instruction())

    response = pipeline.generate_instruction(request)

    assert response.generation_mode == "openai"
    assert response.instruction.steps[0].safety_note
    assert len(response.instruction.control_points) >= 4
    assert len(response.instruction.local_verification_required) >= 3
    assert response.evaluation.overall_score >= 70
