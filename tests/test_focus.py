from types import SimpleNamespace

from app.evaluation.quality import evaluate_instruction
from app.generation import pipeline
from app.generation.focus import focus_instruction_on_request
from app.generation.fallback import generate_fallback_instruction
from app.generation.quality_improver import improve_instruction_quality
from app.schemas.instruction import InstructionRequest


def test_focus_layer_keeps_narrow_emergency_button_request_explicit() -> None:
    request = InstructionRequest(
        task="Составить инструкцию по проверке аварийной кнопки ленточнопильного станка перед запуском",
        instruction_type="inspection",
        industry_profile="manufacturing",
        equipment="Ленточнопильный станок",
        technical_context="Нужно проверить доступность, отсутствие блокировки и фиксацию результата проверки аварийной кнопки.",
    )
    instruction = focus_instruction_on_request(
        improve_instruction_quality(generate_fallback_instruction(request), request),
        request,
    )
    evaluation = evaluate_instruction(instruction, request)
    request_focus = next(item for item in evaluation.criteria if item.criterion == "request_focus")
    combined = " ".join(
        [
            instruction.title,
            instruction.purpose,
            instruction.scope,
            *instruction.control_points,
            *instruction.quality_checklist,
        ]
    ).lower()

    assert "аварийн" in combined
    assert "кноп" in combined
    assert "граница инструкции" in instruction.scope.lower()
    assert request_focus.score >= 80


def test_pipeline_returns_focused_instruction_for_narrow_request(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(openai_enabled=False, openai_api_key=None, openai_model="test", openai_timeout_seconds=1),
    )
    request = InstructionRequest(
        task="Проверить защитное ограждение ленточнопильного станка перед началом работы",
        instruction_type="inspection",
        industry_profile="manufacturing",
        equipment="Ленточнопильный станок",
    )

    response = pipeline.generate_instruction(request)
    request_focus = next(item for item in response.evaluation.criteria if item.criterion == "request_focus")

    assert response.instruction.title.startswith("Инструкция: Проверить защитное ограждение")
    assert "не расширяет задачу" in " ".join(response.instruction.quality_checklist).lower()
    assert request_focus.score >= 80
    assert "request_focus" in response.markdown or "Фокус" in response.instruction.control_points[0]
