import re
from typing import cast

from app.evaluation.safety import analyze_untrusted_context
from app.schemas.instruction import (
    CriterionScore,
    EvaluationCriterion,
    EvaluationRequest,
    InstructionEvaluation,
    InstructionRequest,
    RiskLevel,
    SafetyFinding,
    WorkInstruction,
)


CRITERION_LABELS = {
    "completeness": "Полнота",
    "clarity": "Понятность",
    "input_alignment": "Соответствие входным данным",
    "request_focus": "Фокус на задаче",
    "safety": "Безопасность",
    "logical_sequence": "Логическая последовательность",
    "training_value": "Пригодность для обучения",
    "source_grounding": "Опора на источники",
    "domain_risk_control": "Контроль отраслевых рисков",
    "implementation_readiness": "Готовность к внедрению",
}


def evaluate_instruction_request(request: EvaluationRequest) -> InstructionEvaluation:
    return evaluate_instruction(request.instruction, request.source_request)


def evaluate_instruction(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None = None,
) -> InstructionEvaluation:
    safety_findings = analyze_untrusted_context(
        source_request.technical_context if source_request else None
    )
    criteria = [
        _score_completeness(instruction),
        _score_clarity(instruction),
        _score_input_alignment(instruction, source_request),
        _score_request_focus(instruction, source_request),
        _score_safety(instruction),
        _score_logical_sequence(instruction),
        _score_training_value(instruction),
        _score_source_grounding(instruction, source_request, safety_findings),
        _score_domain_risk_control(instruction, source_request, safety_findings),
        _score_implementation_readiness(instruction),
    ]
    overall = round(sum(item.score for item in criteria) / len(criteria))
    missing = _detect_missing_elements(instruction)
    recommendations = _build_recommendations(criteria, missing, safety_findings)
    risk_level = cast(RiskLevel, _risk_level(overall, criteria, missing, safety_findings))
    expert_notes = _expert_review_notes(instruction, source_request, risk_level, safety_findings)
    return InstructionEvaluation(
        overall_score=overall,
        criteria=criteria,
        missing_elements=missing,
        recommendations=recommendations,
        verdict=_verdict(overall, safety_findings),
        risk_level=risk_level,
        expert_review_required=True,
        expert_review_notes=expert_notes,
        safety_findings=safety_findings,
    )


def _score_completeness(instruction: WorkInstruction) -> CriterionScore:
    checks = {
        "указаны СИЗ": bool(instruction.required_ppe),
        "указаны инструменты и документы": bool(instruction.required_tools),
        "указаны требования безопасности": bool(instruction.safety_requirements),
        "указаны опасные зоны": bool(instruction.hazard_zones),
        "указаны предварительные условия": bool(instruction.prerequisites),
        "есть не менее 4 шагов": len(instruction.steps) >= 4,
        "есть контрольные точки": bool(instruction.control_points),
        "есть действия при нештатной ситуации": bool(instruction.emergency_actions),
    }
    return _criterion("completeness", checks)


def _score_clarity(instruction: WorkInstruction) -> CriterionScore:
    action_lengths = [len(step.action.split()) for step in instruction.steps]
    vague_markers = ["выполнить операцию", "по необходимости", "при необходимости", "уточнить"]
    vague_count = sum(
        1
        for step in instruction.steps
        if any(marker in step.action.lower() for marker in vague_markers)
    )
    checks = {
        "шаги достаточно развернуты": bool(action_lengths) and min(action_lengths) >= 4,
        "у каждого шага есть ожидаемый результат": all(step.expected_result for step in instruction.steps),
        "у большинства шагов есть способ проверки": _share(
            bool(step.verification_method) for step in instruction.steps
        )
        >= 0.7,
        "мало слишком общих формулировок": vague_count <= 1,
    }
    return _criterion("clarity", checks)


def _score_input_alignment(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None,
) -> CriterionScore:
    checks = {
        "сохранена область применения": bool(instruction.scope),
        "сохранено название оборудования": True,
        "сохранен участок": True,
        "учтен технический контекст": True,
    }
    if source_request:
        checks["сохранено название оборудования"] = (
            not source_request.equipment
            or source_request.equipment.lower() in (instruction.equipment or "").lower()
            or source_request.equipment.lower() in instruction.scope.lower()
        )
        checks["сохранен участок"] = (
            not source_request.department
            or source_request.department.lower() in (instruction.department or "").lower()
            or source_request.department.lower() in instruction.scope.lower()
        )
        checks["учтен технический контекст"] = (
            not source_request.technical_context
            or _keyword_overlap(source_request.technical_context, _instruction_text(instruction)) >= 0.12
        )
    return _criterion("input_alignment", checks)


def _score_request_focus(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None,
) -> CriterionScore:
    if not source_request:
        return _criterion(
            "request_focus",
            {
                "есть явная граница задачи": "границ" in instruction.scope.lower() or "конкретн" in instruction.purpose.lower(),
                "шаги не пустые": bool(instruction.steps),
            },
        )

    focus_text = " ".join(
        part
        for part in [
            source_request.task,
            source_request.operation_name or "",
            source_request.equipment or "",
            source_request.department or "",
        ]
        if part
    )
    instruction_text = _instruction_text(instruction)
    focus_tokens = _keywords(focus_text)
    step_focus_share = _share(_keyword_overlap(focus_text, step.action) >= 0.08 for step in instruction.steps)
    boundary_text = " ".join([instruction.purpose, instruction.scope, *instruction.quality_checklist]).lower()
    checks = {
        "название или назначение отражает запрос": _keyword_overlap(focus_text, f"{instruction.title} {instruction.purpose}") >= 0.12,
        "текст инструкции сохраняет ключевые термины запроса": not focus_tokens or _keyword_overlap(focus_text, instruction_text) >= 0.16,
        "большинство шагов связано с задачей": step_focus_share >= 0.6,
        "есть явная граница, не расширяющая задачу": any(word in boundary_text for word in ["границ", "не расшир", "конкретн", "только"]),
        "нет признаков ухода в нерелевантную смежную операцию": not _has_scope_drift(source_request, instruction_text.lower()),
    }
    return _criterion("request_focus", checks)


def _score_safety(instruction: WorkInstruction) -> CriterionScore:
    safety_steps = sum(1 for step in instruction.steps if step.safety_note)
    checks = {
        "указаны СИЗ": bool(instruction.required_ppe),
        "указаны опасные зоны": bool(instruction.hazard_zones),
        "указаны требования безопасности": len(instruction.safety_requirements) >= 3,
        "у большинства шагов есть примечания по безопасности": _safe_ratio(safety_steps, len(instruction.steps)) >= 0.6,
        "есть аварийные действия": len(instruction.emergency_actions) >= 3,
    }
    return _criterion("safety", checks)


def _score_logical_sequence(instruction: WorkInstruction) -> CriterionScore:
    numbers = [step.number for step in instruction.steps]
    checks = {
        "нумерация идет без пропусков": numbers == list(range(1, len(numbers) + 1)),
        "есть подготовительный шаг": bool(instruction.steps)
        and any(
            word in instruction.steps[0].action.lower()
            for word in ["уточнить", "проверить", "подготовить", "сверить", "подтвердить", "определить"]
        ),
        "есть финальная проверка": any(
            word in instruction.steps[-1].action.lower()
            for word in ["проверить", "зафиксировать", "передать", "заверш"]
        )
        if instruction.steps
        else False,
        "контрольные точки связаны с процессом": len(instruction.control_points) >= 3,
    }
    return _criterion("logical_sequence", checks)


def _score_training_value(instruction: WorkInstruction) -> CriterionScore:
    checks = {
        "указан уровень пользователя": bool(instruction.operator_level),
        "описаны типовые ошибки": len(instruction.common_mistakes) >= 3,
        "у шагов есть ожидаемые результаты": all(step.expected_result for step in instruction.steps),
        "у шагов есть проверки": _share(bool(step.verification_method) for step in instruction.steps) >= 0.7,
        "есть чеклист качества": len(instruction.quality_checklist) >= 3,
    }
    return _criterion("training_value", checks)


def _score_source_grounding(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None,
    safety_findings: list[SafetyFinding],
) -> CriterionScore:
    context = source_request.technical_context if source_request else ""
    instruction_text = _instruction_text(instruction)
    checks = {
        "есть входной или найденный контекст": bool(context),
        "контекст отражен в инструкции": not context or _keyword_overlap(context, instruction_text) >= 0.12,
        "нет неподтвержденных точных параметров": not _has_unverified_precise_values(instruction_text),
        "неподтвержденные требования помечены для локальной проверки": _mentions_local_verification(instruction_text),
        "есть типизированное происхождение утверждений": bool(instruction.evidence_claims),
        "непроверенные утверждения не помечены подтвержденными": not any(
            claim.validation_status == "unverified"
            and any(marker in claim.text.casefold() for marker in ["подтвержденн", "confirmed"])
            for claim in instruction.evidence_claims
        ),
        "нет неразрешенных safety-сигналов во входном контексте": not safety_findings,
        "есть список локальных проверок": len(instruction.local_verification_required) >= 2,
    }
    return _criterion("source_grounding", checks)


def _score_domain_risk_control(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None,
    safety_findings: list[SafetyFinding],
) -> CriterionScore:
    profile = source_request.industry_profile if source_request else "general"
    text = _instruction_text(instruction).lower()
    checks = {
        "есть эскалация ответственному лицу": any(word in text for word in ["мастер", "ответствен", "руководител", "специалист"]),
        "есть запрет продолжения при опасности": any(word in text for word in ["не возобновлять", "не продолжать", "запрещ", "остановить"]),
        "учтены профильные риски": _profile_risk_covered(profile, text),
        "нет опасных самовольных действий": not any(word in text for word in ["самостоятельно изменить режим", "обойти блокировку", "отключить защиту"]),
        "нет критических сигналов в непроверенном контексте": not any(
            finding.severity == "critical" for finding in safety_findings
        ),
    }
    return _criterion("domain_risk_control", checks)


def _score_implementation_readiness(instruction: WorkInstruction) -> CriterionScore:
    text = _instruction_text(instruction).lower()
    checks = {
        "есть фиксация результата или отклонений": any(word in text for word in ["зафикс", "журнал", "запис", "расписк", "акт"]),
        "есть критерии приемки или контроль результата": len(instruction.control_points) >= 4 and len(instruction.quality_checklist) >= 3,
        "есть аварийный сценарий": len(instruction.emergency_actions) >= 3,
        "есть явная экспертная проверка перед внедрением": any(word in text for word in ["провер", "ответствен", "технолог", "охране труда"]),
        "есть вопросы для экспертной доработки": len(instruction.expert_review_questions) >= 3,
        "есть неподтвержденные параметры для проверки": bool(instruction.local_verification_required),
        "есть роли согласования": len(instruction.workflow.required_review_roles) >= 2,
        "есть блокеры утверждения": bool(instruction.workflow.approval_blockers),
        "есть следующие действия по внедрению": len(instruction.workflow.next_actions) >= 2,
    }
    return _criterion("implementation_readiness", checks)


def _criterion(name: str, checks: dict[str, bool]) -> CriterionScore:
    passed = [label for label, ok in checks.items() if ok]
    failed = [label for label, ok in checks.items() if not ok]
    score = round(100 * len(passed) / len(checks)) if checks else 0
    return CriterionScore(
        criterion=cast(EvaluationCriterion, name),
        label=CRITERION_LABELS[name],
        score=score,
        strengths=passed,
        issues=failed,
    )


def _detect_missing_elements(instruction: WorkInstruction) -> list[str]:
    missing = []
    if not instruction.required_ppe:
        missing.append("СИЗ")
    if not instruction.hazard_zones:
        missing.append("опасные зоны")
    if len(instruction.steps) < 4:
        missing.append("достаточное количество шагов")
    if not instruction.control_points:
        missing.append("контрольные точки")
    if not instruction.emergency_actions:
        missing.append("действия при нештатной ситуации")
    if not instruction.local_verification_required:
        missing.append("локальные проверки перед внедрением")
    if not instruction.expert_review_questions:
        missing.append("вопросы для экспертной проверки")
    if not instruction.workflow.required_review_roles:
        missing.append("роли согласования")
    if not instruction.workflow.approval_blockers:
        missing.append("блокеры перед утверждением")
    if not instruction.workflow.next_actions:
        missing.append("следующие действия по внедрению")
    return missing


def _build_recommendations(
    criteria: list[CriterionScore],
    missing: list[str],
    safety_findings: list[SafetyFinding],
) -> list[str]:
    recommendations = [
        f"Safety blocker [{finding.code}]: {finding.message}" for finding in safety_findings
    ]
    for criterion in criteria:
        if criterion.score < 80 and criterion.issues:
            recommendations.append(f"Усилить критерий «{criterion.label}»: {criterion.issues[0]}.")
    for item in missing:
        recommendations.append(f"Добавить раздел: {item}.")
    if not recommendations:
        recommendations.append("Инструкция структурно готова для демонстрационного сценария; следующий шаг — экспертная проверка на реальном процессе.")
    recommendations.append("Перед внедрением подтвердить актуальность источников, локальные допуски, режимы и ответственных лиц.")
    return recommendations[:8]


def _verdict(score: int, safety_findings: list[SafetyFinding]) -> str:
    if safety_findings:
        return (
            "Структурная оценка завершена, но применение заблокировано safety-сигналами "
            "до проверки и исправления ответственным специалистом."
        )
    if score >= 90:
        return "Высокое качество: инструкция подходит для демонстрации и дальнейшей экспертной проверки."
    if score >= 75:
        return "Хорошее качество: инструкция применима как черновик, но требует точечной доработки."
    if score >= 60:
        return "Среднее качество: инструкция требует доработки перед использованием в обучении."
    return "Низкое качество: инструкция недостаточно полная для производственного сценария."


def _risk_level(
    criteria_score: int,
    criteria: list[CriterionScore],
    missing: list[str],
    safety_findings: list[SafetyFinding],
) -> str:
    if any(finding.severity == "critical" for finding in safety_findings):
        return "critical"
    if safety_findings:
        return "high"
    weak_safety = any(item.criterion in {"safety", "domain_risk_control"} and item.score < 80 for item in criteria)
    weak_grounding = any(item.criterion == "source_grounding" and item.score < 75 for item in criteria)
    if criteria_score < 60 or (weak_safety and missing):
        return "critical"
    if criteria_score < 75 or weak_safety or weak_grounding:
        return "high"
    if criteria_score < 90:
        return "medium"
    return "low"


def _expert_review_notes(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None,
    risk_level: str,
    safety_findings: list[SafetyFinding],
) -> list[str]:
    profile = source_request.industry_profile if source_request else "general"
    notes = [
        *[f"Safety blocker [{finding.code}]: {finding.message}" for finding in safety_findings],
        "Проверить актуальность публичных источников и применимость к конкретному объекту/оборудованию.",
        "Подтвердить локальные режимы, допуски, ответственных лиц и форму фиксации результата.",
    ]
    if profile in {"construction", "manufacturing", "housing_utilities", "transport", "food_production"}:
        notes.append("Проверить требования допуска, СИЗ, опасные зоны и порядок остановки работ.")
    if profile in {"healthcare", "emergency_response"}:
        notes.append("Проверить соответствие утвержденным медицинским/аварийным регламентам и полномочиям исполнителей.")
    if risk_level in {"high", "critical"}:
        notes.append("До применения требуется обязательная доработка специалистом профильного направления.")
    return notes[:8]


def _has_unverified_precise_values(text: str) -> bool:
    value_patterns = [
        r"\b\d+([,.]\d+)?\s*(мм|см|м|кг|нм|об/мин|rpm|бар|мпа|°c|градус)",
        r"\b\d+([,.]\d+)?\s*(сек|мин|час)",
    ]
    lowered = text.lower()
    has_value = any(re.search(pattern, lowered) for pattern in value_patterns)
    if not has_value:
        return False
    return not _mentions_local_verification(lowered)


def _mentions_local_verification(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in [
            "проверить локаль",
            "уточнить локаль",
            "согласно документации",
            "по документации участка",
            "требует проверки",
            "подтвердить",
        ]
    )


def _profile_risk_covered(profile: str, text: str) -> bool:
    profile_terms = {
        "manufacturing": ["огражд", "аварийн", "опасн"],
        "construction": ["огражд", "сиз", "зон"],
        "occupational_safety": ["останов", "сообщ", "ответствен"],
        "emergency_response": ["эвакуац", "оповещ", "безопасн"],
        "public_service": ["документ", "заявител", "персональн"],
        "housing_utilities": ["локализ", "перекры", "диспетчер"],
        "healthcare": ["санитар", "сиз", "отход"],
        "education": ["инструктаж", "учен", "наблюден"],
        "food_production": ["санитар", "маркиров", "парт"],
        "transport": ["осмотр", "документ", "неисправ"],
        "information_security": ["ссыл", "вложен", "иб"],
        "general": ["опасн", "провер", "ответствен"],
    }
    terms = profile_terms.get(profile, profile_terms["general"])
    return any(term in text for term in terms)


def _has_scope_drift(source_request: InstructionRequest, instruction_text: str) -> bool:
    task_text = " ".join([source_request.task, source_request.operation_name or ""]).lower()
    drift_markers = {
        "equipment_startup": ["остановить оборудование", "передать смену"],
        "equipment_shutdown": ["выполнить запуск", "разрешение на запуск"],
        "inspection": ["выполнить ремонт", "устранить дефект", "заменить узел"],
        "maintenance": ["начать производство", "основная операция"],
    }
    allowed = task_text + " " + (source_request.technical_context or "").lower()
    for marker in drift_markers.get(source_request.instruction_type, []):
        if marker in instruction_text and marker not in allowed:
            return True
    return False


def _share(values) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(1 for item in items if item) / len(items)


def _safe_ratio(value: int, total: int) -> float:
    if total == 0:
        return 0.0
    return value / total


def _keyword_overlap(source: str, target: str) -> float:
    source_words = _keywords(source)
    if not source_words:
        return 1.0
    target_words = _keywords(target)
    return len(source_words & target_words) / len(source_words)


def _keywords(text: str) -> set[str]:
    stopwords = {
        "и",
        "в",
        "на",
        "по",
        "для",
        "или",
        "при",
        "что",
        "после",
        "перед",
        "должен",
        "должна",
        "необходимо",
    }
    return {
        word.strip(".,:;!?()[]").lower()
        for word in text.split()
        if len(word.strip(".,:;!?()[]")) >= 5 and word.strip(".,:;!?()[]").lower() not in stopwords
    }


def _instruction_text(instruction: WorkInstruction) -> str:
    parts = [
        instruction.title,
        instruction.purpose,
        instruction.scope,
        instruction.department or "",
        instruction.equipment or "",
        *instruction.required_ppe,
        *instruction.required_tools,
        *instruction.safety_requirements,
        *instruction.hazard_zones,
        *instruction.prerequisites,
        *instruction.control_points,
        *instruction.quality_checklist,
        *instruction.emergency_actions,
        *instruction.common_mistakes,
        *instruction.observed_facts,
        *instruction.local_verification_required,
        *instruction.expert_review_questions,
    ]
    for step in instruction.steps:
        parts.extend(
            [
                step.action,
                step.expected_result,
                step.safety_note or "",
                step.verification_method or "",
                *step.common_mistakes,
            ]
        )
    return " ".join(parts)
