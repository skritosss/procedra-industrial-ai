import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.instruction import InstructionRequest
from app.schemas.instruction import IndustryProfile, InstructionType
from app.schemas.instruction import InstructionStep, WorkInstruction


EXAMPLE_FILES = [
    Path("examples/text_request.json"),
    *Path("examples/industrial_cases").glob("*.json"),
]


def test_all_examples_are_valid_instruction_requests() -> None:
    assert EXAMPLE_FILES
    for path in EXAMPLE_FILES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        request = InstructionRequest.model_validate(payload)
        assert request.task


def test_operation_template_manifest_is_broad_and_valid() -> None:
    templates = json.loads(Path("examples/operation_templates.json").read_text(encoding="utf-8"))
    ids = [template["id"] for template in templates]
    profiles = {template["industry_profile"] for template in templates}

    assert len(templates) >= 10
    assert len(ids) == len(set(ids))
    assert {"manufacturing", "construction", "occupational_safety", "emergency_response", "housing_utilities"}.issubset(
        profiles
    )
    for template in templates:
        assert template["title_ru"]
        assert template["title_en"]
        assert template["category"]
        assert template["instruction_type"] in InstructionType.__args__
        assert template["industry_profile"] in IndustryProfile.__args__


def test_blank_optional_request_fields_are_normalized() -> None:
    request = InstructionRequest(
        task="Подготовить рабочее место оператора перед запуском оборудования",
        department="   ",
        equipment="",
        operation_name="  Подготовка рабочего места  ",
    )

    assert request.department is None
    assert request.equipment is None
    assert request.operation_name == "Подготовка рабочего места"


def test_instruction_string_lists_are_cleaned() -> None:
    instruction = WorkInstruction(
        title=" Инструкция ",
        purpose=" Проверка ",
        scope=" Участок ",
        operator_level=" Новый оператор ",
        required_ppe=[" Очки ", " "],
        required_tools=[" Документ "],
        safety_requirements=[" Проверить безопасность "],
        hazard_zones=[" Рабочая зона "],
        prerequisites=[" Рабочее место готово "],
        steps=[
            InstructionStep(
                number=1,
                action=" Выполнить проверку ",
                expected_result=" Проверка выполнена ",
                safety_note=" ",
                common_mistakes=[" Пропуск проверки ", ""],
            )
        ],
        control_points=[" Контроль выполнен "],
        quality_checklist=[" Результат проверен "],
        emergency_actions=[" Остановить операцию "],
        common_mistakes=[" Ошибка "],
    )

    assert instruction.title == "Инструкция"
    assert instruction.required_ppe == ["Очки"]
    assert instruction.steps[0].safety_note is None
    assert instruction.steps[0].common_mistakes == ["Пропуск проверки"]


def test_instruction_rejects_empty_required_lists() -> None:
    with pytest.raises(ValidationError):
        WorkInstruction(
            title="Инструкция",
            purpose="Проверка",
            scope="Участок",
            operator_level="Новый оператор",
            required_ppe=[" "],
            required_tools=["Документ"],
            safety_requirements=["Проверить безопасность"],
            hazard_zones=["Рабочая зона"],
            prerequisites=["Рабочее место готово"],
            steps=[
                InstructionStep(
                    number=1,
                    action="Выполнить проверку",
                    expected_result="Проверка выполнена",
                )
            ],
            control_points=["Контроль выполнен"],
            quality_checklist=["Результат проверен"],
            emergency_actions=["Остановить операцию"],
            common_mistakes=["Ошибка"],
        )


def test_instruction_rejects_non_sequential_step_numbers() -> None:
    with pytest.raises(ValidationError):
        WorkInstruction(
            title="Инструкция",
            purpose="Проверка",
            scope="Участок",
            operator_level="Новый оператор",
            required_ppe=["Очки"],
            required_tools=["Документ"],
            safety_requirements=["Проверить безопасность"],
            hazard_zones=["Рабочая зона"],
            prerequisites=["Рабочее место готово"],
            steps=[
                InstructionStep(
                    number=2,
                    action="Выполнить проверку",
                    expected_result="Проверка выполнена",
                )
            ],
            control_points=["Контроль выполнен"],
            quality_checklist=["Результат проверен"],
            emergency_actions=["Остановить операцию"],
            common_mistakes=["Ошибка"],
        )
