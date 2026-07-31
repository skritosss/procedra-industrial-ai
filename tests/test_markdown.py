from app.generation.markdown import render_instruction_markdown
from app.schemas.instruction import InstructionStep, StepFrameLink, WorkInstruction


def test_render_instruction_markdown_contains_core_sections() -> None:
    instruction = WorkInstruction(
        title="Производственная инструкция",
        purpose="Проверить отображение.",
        scope="Тестовый производственный сценарий.",
        department="Тестовый участок",
        equipment="Тестовое оборудование",
        operator_level="Новый оператор",
        required_ppe=["Очки"],
        required_tools=["Инструмент A"],
        safety_requirements=["Проверить безопасность"],
        hazard_zones=["Опасная зона"],
        prerequisites=["Рабочее место готово"],
        steps=[
            InstructionStep(
                number=1,
                action="Выполнить действие",
                expected_result="Действие выполнено",
                safety_note="Не обходить защитные устройства",
                verification_method="Визуальный контроль",
            )
        ],
        control_points=["Контрольная точка"],
        quality_checklist=["Результат проверен"],
        emergency_actions=["Остановить операцию"],
        common_mistakes=["Пропуск проверки"],
        observed_facts=["Факт из входных данных"],
        local_verification_required=["Проверить локальный регламент"],
        expert_review_questions=["Кто подтверждает допуск?"],
    )

    markdown = render_instruction_markdown(instruction)

    assert "# Производственная инструкция" in markdown
    assert "## Порядок выполнения" in markdown
    assert "## Матрица ответственности" in markdown
    assert "## Роли для согласования" in markdown
    assert "## Блокеры перед утверждением" in markdown
    assert "## Следующие действия по внедрению" in markdown
    assert "## Критерии приемки результата" in markdown
    assert "## Утверждения из входных данных" in markdown
    assert "## Происхождение и статус утверждений" in markdown
    assert "## Что требуется проверить локально" in markdown
    assert "## Вопросы для экспертной проверки" in markdown
    assert "## Ограничения и проверка перед внедрением" in markdown
    assert "Ожидаемый результат: Действие выполнено" in markdown
    assert "## Действия при нештатной ситуации" in markdown


def test_render_instruction_markdown_includes_step_frame_links() -> None:
    instruction = WorkInstruction(
        title="Производственная инструкция",
        purpose="Проверить отображение.",
        scope="Тестовый производственный сценарий.",
        operator_level="Новый оператор",
        required_ppe=["Очки"],
        required_tools=["Инструмент A"],
        safety_requirements=["Проверить безопасность"],
        hazard_zones=["Опасная зона"],
        prerequisites=["Рабочее место готово"],
        steps=[
            InstructionStep(
                number=1,
                action="Выполнить действие",
                expected_result="Действие выполнено",
            )
        ],
        control_points=["Контрольная точка"],
        quality_checklist=["Результат проверен"],
        emergency_actions=["Остановить операцию"],
        common_mistakes=["Пропуск проверки"],
    )

    markdown = render_instruction_markdown(
        instruction,
        [
            StepFrameLink(
                step_number=1,
                frame_index=42,
                timestamp_seconds=37,
                reason="Кадр связан с шагом.",
                confidence=0.72,
            )
        ],
    )

    assert "Видео: 00:37, кадр 42, уверенность 0.72" in markdown
    assert "Причина связи: Кадр связан с шагом." in markdown
