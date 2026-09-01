from app.generation.fallback import generate_fallback_instruction
from app.generation.profile_specifics import specifics_for
from app.schemas.instruction import InstructionRequest


def test_industry_block_attaches_to_the_work_not_the_department() -> None:
    """A trigger has to name the work. "Монтажный участок" is where a person is
    based, not what they are doing, and it used to pull fall protection into a
    ground-level hot-work permit."""
    assert not specifics_for("construction", "workplace_preparation", "Подготовка зоны огневых работ. Монтажный участок")
    assert specifics_for("construction", "workplace_preparation", "Монтаж ограждений на кровле здания")


def test_a_dispatcher_is_not_sent_down_a_manhole() -> None:
    """The utilities block applies to field work. Enriched context mentions
    manholes for every utilities request, which is why triggers read only what
    the user asked for."""
    request = InstructionRequest(
        task="Составить инструкцию диспетчера ЖКХ при обращении о протечке в многоквартирном доме",
        industry_profile="housing_utilities",
        department="Аварийно-диспетчерская служба",
        equipment="Диспетчерское рабочее место",
        technical_context="Колодец, коллектор, загазованность: фрагменты найденной документации.",
    )
    text = " ".join(step.action for step in generate_fallback_instruction(request).steps)
    assert "наряд-допуск" not in text.lower()


def test_maintenance_gains_lockout_steps_and_startup_does_not() -> None:
    def steps(instruction_type: str, task: str) -> list[str]:
        request = InstructionRequest(
            task=task, industry_profile="manufacturing", instruction_type=instruction_type
        )
        return [step.action for step in generate_fallback_instruction(request).steps]

    maintenance = steps("maintenance", "Техническое обслуживание пресса на участке")
    startup = steps("equipment_startup", "Запуск пресса на участке после простоя")
    assert any("Не включать" in action for action in maintenance)
    assert not any("Не включать" in action for action in startup)


def test_added_steps_are_renumbered_without_gaps() -> None:
    request = InstructionRequest(
        task="Осмотр канализационного колодца перед началом работ",
        industry_profile="housing_utilities",
        instruction_type="inspection",
    )
    numbers = [step.number for step in generate_fallback_instruction(request).steps]
    assert numbers == list(range(1, len(numbers) + 1))


def test_a_request_that_does_not_match_its_profile_is_flagged() -> None:
    """The evaluator judges how well a draft answers the request. It cannot see
    that the request itself was filed under the wrong industry, and a stationery
    count submitted as manufacturing scores well precisely because the answer
    fits the question."""
    from app.evaluation.quality import evaluate_instruction

    request = InstructionRequest(
        task="Составить инструкцию по инвентаризации канцелярии на складе офиса",
        operation_name="Инвентаризация канцелярии",
        department="Административный склад",
        equipment="Стеллаж для канцелярии",
        industry_profile="manufacturing",
    )
    evaluation = evaluate_instruction(generate_fallback_instruction(request), request)
    assert any("не похожа на отраслевой профиль" in item for item in evaluation.recommendations)


def test_every_demo_scenario_matches_its_own_profile() -> None:
    """A vocabulary that flags correct requests would train people to ignore it."""
    import json
    from pathlib import Path

    from app.generation.industry_profiles import request_matches_profile

    scenarios = json.loads(
        (Path(__file__).resolve().parents[1] / "examples" / "demo_scenarios.json").read_text(
            encoding="utf-8"
        )
    )
    for scenario in scenarios:
        payload = scenario["payload"]
        described = " ".join(
            part
            for part in [
                payload.get("task", ""),
                payload.get("operation_name") or "",
                payload.get("equipment") or "",
                payload.get("department") or "",
            ]
            if part
        )
        assert request_matches_profile(payload["industry_profile"], described), scenario["id"]
