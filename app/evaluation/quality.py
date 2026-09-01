from collections.abc import Mapping
import re
from typing import cast

from app.evaluation import regulatory
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
    "executability": "Исполнимость на месте",
    "regulatory_structure": "Соответствие обязательной структуре",
}


_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "--",
        "—",
        "n/a",
        "na",
        "tbd",
        "нет",
        "нет данных",
        "не указано",
        "не указан",
        "не указана",
        "не определено",
        "не определён",
        "не определен",
        "не применимо",
        "отсутствует",
        "уточнить",
        "выполнено",
        "готово",
        "ок",
        "ok",
        "контроль",
        "проверка",
        "безопасность",
    }
)
CRITERION_WEIGHTS = {
    "safety": 3.0,
    "domain_risk_control": 2.0,
    "source_grounding": 2.0,
    "completeness": 1.5,
    "request_focus": 1.5,
    "clarity": 1.0,
    "logical_sequence": 1.0,
    "input_alignment": 1.0,
    "implementation_readiness": 1.0,
    "training_value": 0.5,
    "executability": 1.5,
    "regulatory_structure": 2.0,
}
SAFETY_CRITICAL_CRITERIA = ("safety", "domain_risk_control")
# Structural completeness is not verification. Until a named reviewer has
# validated at least one claim, the document cannot reach the top of the scale.
UNVERIFIED_DRAFT_CEILING = 95
SAFETY_FLOOR = 90

_MIN_SUBSTANTIVE_CHARS = 4
_SUBSTANTIVE_SHARE_THRESHOLD = 0.8
_CHECK_PASS_THRESHOLD = 0.95


def _check_value(outcome: bool | float) -> float:
    if isinstance(outcome, bool):
        return 1.0 if outcome else 0.0
    return max(0.0, min(1.0, float(outcome)))


def _is_substantive(value: str | None) -> bool:
    """Tell a filled-in field from one that only looks filled in.

    A model that does not know an answer rarely leaves the field empty — the
    schema forbids that. It writes «не указано», «—» or «Выполнено». Those
    entries pass a non-empty check and carry no information, so every list and
    free-text check has to look at the content rather than at the length.

    Length alone cannot decide this. A single word is a perfectly good PPE entry
    («Спецодежда», «Каска»), so requiring two words would reject correct lists.
    What separates a real entry from a filler one is the wording itself, which is
    why the decision rests on an explicit placeholder vocabulary.
    """
    if value is None:
        return False
    cleaned = " ".join(value.split()).strip(" .;:!?—-")
    if len(cleaned) < _MIN_SUBSTANTIVE_CHARS:
        return False
    if cleaned.casefold() in _PLACEHOLDER_VALUES:
        return False
    return any(char.isalpha() for char in cleaned)


def _substantive_share(values: list[str]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if _is_substantive(value)) / len(values)


def _is_substantive_list(values: list[str], minimum: int = 1) -> bool:
    substantive = [value for value in values if _is_substantive(value)]
    if len(substantive) < minimum:
        return False
    return _substantive_share(values) >= _SUBSTANTIVE_SHARE_THRESHOLD


def _distinct_share(values: list[str]) -> float:
    if not values:
        return 0.0
    normalized = [" ".join(value.split()).casefold() for value in values]
    return len(set(normalized)) / len(normalized)


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
        _score_executability(instruction),
        _score_regulatory_structure(instruction, source_request),
    ]
    overall = _unverified_draft_ceiling(instruction, _overall_score(criteria))
    missing = _detect_missing_elements(instruction)
    recommendations = _build_recommendations(criteria, missing, safety_findings)
    risk_level = cast(RiskLevel, _risk_level(overall, criteria, missing, safety_findings))
    expert_notes = _expert_review_notes(instruction, source_request, risk_level, safety_findings)
    profile = source_request.industry_profile if source_request else "general"
    return InstructionEvaluation(
        regulatory_sources=list(regulatory.cited_documents(profile)),
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


def _overall_score(criteria: list[CriterionScore]) -> int:
    """Combine the criteria, then refuse to score above the safety criteria.

    Two properties matter here and neither was present while the overall score
    was a plain average of ten equal criteria.

    First, the criteria are not equally important. An instruction with a weak
    training value is inconvenient; an instruction with weak hazard control is
    dangerous. The weights are declared in `CRITERION_WEIGHTS` rather than being
    implied by how many checks each criterion happens to contain.

    Second, an average lets nine healthy criteria hide one broken one. A draft
    whose PPE list says «не указано» still scored in the nineties, because the
    remaining criteria carried it. So once a safety-critical criterion falls
    below `SAFETY_FLOOR`, it becomes the ceiling for the whole document: an
    instruction cannot be rated better than its own safety.

    The ceiling deliberately applies only below the floor. An unconditional
    `min()` would pin the overall score to the safety criterion even on a healthy
    document, and every other kind of damage — off-topic steps, repeated actions,
    unsupported values — would stop moving the number at all.
    """
    weighted = sum(item.score * CRITERION_WEIGHTS.get(item.criterion, 1.0) for item in criteria)
    total_weight = sum(CRITERION_WEIGHTS.get(item.criterion, 1.0) for item in criteria)
    average = weighted / total_weight if total_weight else 0.0
    weakest_safety = min(
        (item.score for item in criteria if item.criterion in SAFETY_CRITICAL_CRITERIA),
        default=100,
    )
    if weakest_safety < SAFETY_FLOOR:
        return round(min(average, weakest_safety))
    return round(average)


def _unverified_draft_ceiling(instruction: WorkInstruction, score: int) -> int:
    """Hold back the top of the scale until a person has confirmed something.

    The product's own claim is that it produces a draft requiring expert review.
    A draft that scores 100 contradicts that in the same document: the reader is
    told the text is unverified and simultaneously shown a perfect mark. The
    ceiling is not a penalty for a fault — nothing is wrong with the structure —
    it is the difference between "complete" and "confirmed", which the number had
    been quietly collapsing.

    A single validated claim lifts it, because at that point a named reviewer has
    taken responsibility for part of the content.
    """
    if any(claim.validation_record is not None for claim in instruction.evidence_claims):
        return score
    # Scaled, not clipped. Clipping at the ceiling made every draft score exactly
    # the same number, which removed the only thing the score is for: telling one
    # document from another. Scaling keeps the ordering and still puts the top of
    # the scale out of reach until a person has confirmed something.
    return round(score * UNVERIFIED_DRAFT_CEILING / 100)


def _score_completeness(instruction: WorkInstruction) -> CriterionScore:
    checks = {
        "указаны СИЗ": _is_substantive_list(instruction.required_ppe),
        "указаны инструменты и документы": _is_substantive_list(instruction.required_tools),
        "указаны требования безопасности": _is_substantive_list(instruction.safety_requirements),
        "указаны опасные зоны": _is_substantive_list(instruction.hazard_zones),
        "указаны предварительные условия": _is_substantive_list(instruction.prerequisites),
        "есть не менее 4 шагов": len(instruction.steps) >= 4,
        "есть контрольные точки": _is_substantive_list(instruction.control_points, minimum=3)
        and _distinct_share(instruction.control_points) >= 0.8,
        "есть действия при нештатной ситуации": _is_substantive_list(instruction.emergency_actions),
    }
    issue_labels = {
        "указаны СИЗ": "список СИЗ заполнен формально",
        "указаны инструменты и документы": "список инструментов и документов заполнен формально",
        "указаны требования безопасности": "требования безопасности заполнены формально",
        "указаны опасные зоны": "опасные зоны заполнены формально",
        "указаны предварительные условия": "предварительные условия заполнены формально",
        "есть не менее 4 шагов": "шагов меньше четырёх",
        "есть контрольные точки": "контрольные точки формальные или повторяются",
        "есть действия при нештатной ситуации": "действия при нештатной ситуации заполнены формально",
    }
    return _criterion("completeness", checks, issue_labels)


def _score_clarity(instruction: WorkInstruction) -> CriterionScore:
    action_lengths = [len(step.action.split()) for step in instruction.steps]
    vague_markers = ["выполнить операцию", "по необходимости", "при необходимости", "уточнить"]
    vague_count = sum(
        1
        for step in instruction.steps
        if any(marker in step.action.lower() for marker in vague_markers)
    )
    actions = [step.action for step in instruction.steps]
    checks = {
        "шаги достаточно развернуты": bool(action_lengths) and min(action_lengths) >= 4,
        "у каждого шага есть содержательный ожидаемый результат": all(
            _is_substantive(step.expected_result) for step in instruction.steps
        ),
        "у большинства шагов есть способ проверки": _share(
            _is_substantive(step.verification_method) for step in instruction.steps
        ),
        "мало слишком общих формулировок": vague_count <= 1,
        "шаги не повторяют друг друга": _distinct_share(actions),
    }
    issue_labels = {
        "шаги достаточно развернуты": "часть шагов сформулирована слишком коротко",
        "у каждого шага есть содержательный ожидаемый результат": (
            "ожидаемый результат части шагов формален"
        ),
        "у большинства шагов есть способ проверки": "у части шагов нет способа проверки",
        "мало слишком общих формулировок": "слишком много общих формулировок",
        "шаги не повторяют друг друга": "шаги повторяются",
    }
    return _criterion("clarity", checks, issue_labels)


def _score_input_alignment(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None,
) -> CriterionScore:
    checks = {
        # Not `bool(scope)`: the schema already requires a non-empty string, so
        # that phrasing described a check that could not fail. The label claims
        # the scope still belongs to this request, and that is what is measured.
        "сохранена область применения": _is_substantive(instruction.scope),
        "сохранено название оборудования": True,
        "сохранен участок": True,
        "учтен технический контекст": True,
    }
    if source_request:
        checks["сохранена область применения"] = _is_substantive(instruction.scope) and (
            _keyword_overlap(source_request.task, instruction.scope) >= 0.2
            or bool(
                source_request.operation_name
                and source_request.operation_name.lower() in instruction.scope.lower()
            )
        )
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
    # There is no check here for "most steps relate to the task", and the reason
    # is worth keeping. It compared each step's wording with the request, and the
    # measured overlaps on a correct maintenance draft were 0.00-0.40 with no
    # threshold separating the good steps from the bad: "stop the machine,
    # release the pressure" shares nothing with "maintenance of a lathe" and is
    # plainly part of it, while a generic template that repeats the request in
    # every step scored full marks. The metric rewarded echoing the question over
    # answering it, and it cost industry-specific content points for being
    # specific. Tuning the threshold would have been fitting the number to the
    # documents in front of it. Drift is still caught: the checks below judge the
    # document as a whole, and off-topic steps move them.
    boundary_text = " ".join([instruction.purpose, instruction.scope, *instruction.quality_checklist]).lower()
    document_body = " ".join(
        [
            instruction.purpose,
            instruction.scope,
            *instruction.safety_requirements,
            *instruction.hazard_zones,
            *instruction.prerequisites,
            *instruction.control_points,
            *instruction.quality_checklist,
            *instruction.emergency_actions,
        ]
    )
    # Measured on the demo set before the threshold was chosen: steps of a sound
    # draft overlap the rest of its own document at 0.11-1.0, mostly above 0.4,
    # while steps swapped for another procedure sit at 0.0-0.2. A step whose
    # words appear nowhere else in the document it belongs to is the signal.
    step_coherence = _share(
        _keyword_overlap(step.action, document_body) >= 0.25 for step in instruction.steps
    )
    checks = {
        "название или назначение отражает запрос": _keyword_overlap(focus_text, f"{instruction.title} {instruction.purpose}") >= 0.12,
        "текст инструкции сохраняет ключевые термины запроса": not focus_tokens or _keyword_overlap(focus_text, instruction_text) >= 0.16,
        "шаги согласованы с остальной инструкцией": step_coherence,
        "есть явная граница, не расширяющая задачу": any(word in boundary_text for word in ["границ", "не расшир", "конкретн", "только"]),
        "нет признаков ухода в нерелевантную смежную операцию": not _has_scope_drift(source_request, instruction_text.lower()),
    }
    issue_labels = {
        "большинство шагов связано с задачей": "часть шагов не связана с задачей запроса",
        "название или назначение отражает запрос": "название и назначение слабо отражают запрос",
        "текст инструкции сохраняет ключевые термины запроса": (
            "в тексте инструкции потеряны ключевые термины запроса"
        ),
        "есть явная граница, не расширяющая задачу": "нет явной границы задачи",
        "нет признаков ухода в нерелевантную смежную операцию": (
            "есть признаки ухода в нерелевантную смежную операцию"
        ),
    }
    return _criterion("request_focus", checks, issue_labels)


def _score_safety(instruction: WorkInstruction) -> CriterionScore:
    safety_steps = sum(1 for step in instruction.steps if _is_substantive(step.safety_note))
    checks = {
        "указаны СИЗ": _is_substantive_list(instruction.required_ppe),
        "указаны опасные зоны": _is_substantive_list(instruction.hazard_zones),
        "указаны требования безопасности": _is_substantive_list(
            instruction.safety_requirements, minimum=3
        ),
        "у большинства шагов есть примечания по безопасности": _safe_ratio(safety_steps, len(instruction.steps)),
        "есть аварийные действия": _is_substantive_list(instruction.emergency_actions, minimum=3),
        "опасные зоны адресованы в тексте": _hazard_zones_addressed(instruction),
    }
    issue_labels = {
        "указаны СИЗ": "список СИЗ заполнен формально",
        "указаны опасные зоны": "опасные зоны заполнены формально",
        "указаны требования безопасности": "требований безопасности мало или они формальны",
        "у большинства шагов есть примечания по безопасности": (
            "у части шагов нет содержательного примечания по безопасности"
        ),
        "есть аварийные действия": "аварийных действий мало или они формальны",
        "опасные зоны адресованы в тексте": (
            "часть заявленных опасных зон нигде не адресована"
        ),
    }
    return _criterion("safety", checks, issue_labels)


def _hazard_zones_addressed(instruction: WorkInstruction) -> float:
    """Check that a declared hazard zone is actually handled somewhere.

    Listing a hazard and then never mentioning it again is the failure mode this
    catches: the completeness check sees a filled list, and nothing else notices
    that no step, requirement or emergency action refers to that zone.
    """
    zones = [zone for zone in instruction.hazard_zones if _is_substantive(zone)]
    if not zones:
        return 0.0
    body = " ".join(
        [
            *instruction.safety_requirements,
            *instruction.control_points,
            *instruction.emergency_actions,
            *[step.action for step in instruction.steps],
            *[step.safety_note or "" for step in instruction.steps],
        ]
    ).casefold()
    addressed = sum(1 for zone in zones if _keyword_overlap(zone, body) >= 0.5)
    return addressed / len(zones)


# "подтвердить" and "проверить" open a procedure as often as "подготовить" does;
# without them a maintenance draft that starts by confirming the work order was
# judged to have no preparatory step at all.
_PREPARATION_MARKERS = (
    "подготовить", "сверить", "уточнить", "убедиться", "определить", "получить",
    "подтвердить", "проверить", "осмотреть", "ознакомиться",
)
_COMPLETION_MARKERS = ("зафиксировать", "передать", "заверш", "оформить", "сдать", "занести в журнал")


def _score_logical_sequence(instruction: WorkInstruction) -> CriterionScore:
    # Sequential numbering is not checked here: the schema rejects a document
    # whose steps are not numbered from 1 without gaps, so a criterion asking
    # the same question could never fail. Keeping it inflated the count of
    # checks without adding a single one that can catch anything.
    checks = {
        "есть подготовительный шаг": bool(instruction.steps)
        and _matches_any(instruction.steps[0].action, _PREPARATION_MARKERS),
        "есть финальная проверка": bool(instruction.steps)
        and _matches_any(instruction.steps[-1].action, _COMPLETION_MARKERS),
        "подготовка идет раньше завершения": _preparation_precedes_completion(instruction),
        # Counting entries answered a different question, and completeness
        # already asks it. Relatedness is whether a control point refers to the
        # work the steps describe.
        "контрольные точки связаны с процессом": _control_points_follow_steps(instruction),
    }
    issue_labels = {
        "нумерация идет без пропусков": "нумерация шагов нарушена",
        "есть подготовительный шаг": "первый шаг не является подготовительным",
        "есть финальная проверка": "последний шаг не завершает работу",
        "подготовка идет раньше завершения": "подготовительные действия стоят после завершающих",
        "контрольные точки связаны с процессом": "контрольных точек слишком мало",
    }
    return _criterion("logical_sequence", checks, issue_labels)


def _matches_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in markers)


def _preparation_precedes_completion(instruction: WorkInstruction) -> bool:
    """Check the order of the work, not the order of the numbers.

    The schema already guarantees that `number` runs 1..n, so a numbering check
    can never fail on a document that reached evaluation. What can still be wrong
    is the order of the actions themselves: a draft that files the results first
    and prepares the workplace last is numbered perfectly and is still unusable.

    The marker sets are kept disjoint on purpose. While «проверить» counted as
    both preparation and completion, a fully reversed instruction satisfied both
    checks and the criterion stayed at its maximum.
    """
    preparation = [
        index for index, step in enumerate(instruction.steps) if _matches_any(step.action, _PREPARATION_MARKERS)
    ]
    completion = [
        index for index, step in enumerate(instruction.steps) if _matches_any(step.action, _COMPLETION_MARKERS)
    ]
    if not preparation or not completion:
        return True
    return min(preparation) < max(completion)


_RELATED_CONTROL_POINTS_EXPECTED = 3


def _control_points_follow_steps(instruction: WorkInstruction) -> float:
    """Share of control points that refer to what the steps actually do.

    A list of four checks about the canteen rota is still four checks. Without
    this the criterion accepted any list of the right length.
    """
    points = [point for point in instruction.control_points if _is_substantive(point)]
    if not points:
        return 0.0
    step_text = " ".join(
        [step.action for step in instruction.steps]
        + [step.expected_result for step in instruction.steps]
    )
    related = sum(1 for point in points if _keyword_overlap(point, step_text) >= 0.25)
    # A share of the whole list would be the wrong measure: general points like
    # "PPE prepared" are legitimate and refer to no particular step. What must
    # not happen is a list where nothing refers to this procedure at all.
    return min(related, _RELATED_CONTROL_POINTS_EXPECTED) / _RELATED_CONTROL_POINTS_EXPECTED


def _score_training_value(instruction: WorkInstruction) -> CriterionScore:
    checks = {
        "указан уровень пользователя": _is_substantive(instruction.operator_level),
        "описаны типовые ошибки": len(instruction.common_mistakes) >= 3,
        # The schema already requires a non-empty expected_result, so testing for
        # presence tested nothing. "Выполнено" on every step is the real failure.
        "у шагов есть ожидаемые результаты": _share(
            _is_substantive(step.expected_result) for step in instruction.steps
        ),
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
        "нет неподтвержденных точных параметров": _precise_values_are_covered(instruction),
        "неподтвержденные требования помечены для локальной проверки": _mentions_local_verification(instruction_text),
        "есть типизированное происхождение утверждений": _is_substantive_list(
            [claim.text for claim in instruction.evidence_claims]
        ),
        "непроверенные утверждения не помечены подтвержденными": not any(
            claim.validation_status == "unverified"
            and any(marker in claim.text.casefold() for marker in ["подтвержденн", "confirmed"])
            for claim in instruction.evidence_claims
        ),
        "нет неразрешенных safety-сигналов во входном контексте": not safety_findings,
        "есть список локальных проверок": len(instruction.local_verification_required) >= 2,
    }
    issue_labels = {
        "нет неразрешенных safety-сигналов во входном контексте": (
            "обнаружены неразрешенные safety-сигналы во входном контексте"
        ),
        "непроверенные утверждения не помечены подтвержденными": (
            "непроверенные утверждения помечены как подтвержденные"
        ),
        "нет неподтвержденных точных параметров": (
            "в тексте есть точные параметры без подтверждения"
        ),
    }
    return _criterion("source_grounding", checks, issue_labels)


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
    issue_labels = {
        "нет критических сигналов в непроверенном контексте": (
            "обнаружен критический сигнал в непроверенном контексте"
        ),
        "нет опасных самовольных действий": (
            "в тексте есть признаки опасных самовольных действий"
        ),
    }
    return _criterion("domain_risk_control", checks, issue_labels)


_ROLE_MARKERS = ("оператор", "мастер", "технолог", "специалист", "ответственн", "руководител", "наладчик")
_VAGUE_REFERENCES = (
    "согласно документации",
    "по инструкции предприятия",
    "в установленном порядке",
    "по действующим нормам",
    "в соответствии с регламентом",
)
_UNIT_MARKERS = (
    "мм", "см", "м", "кг", "г", "н·м", "нм", "бар", "мпа", "па", "°c", "с", "сек",
    "мин", "ч", "в", "а", "квт", "об/мин", "%", "л",
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _score_regulatory_structure(
    instruction: WorkInstruction,
    source_request: InstructionRequest | None,
) -> CriterionScore:
    """Coverage of published requirements, general and industry-specific.

    Every other criterion measures a property we chose. This one measures
    requirements that exist whether we agree with them or not, which is what
    lets a customer's safety engineer verify the mapping against documents they
    already have. The requirements live in `app/evaluation/regulatory.py`, each
    naming its source and, where it was read in the official text, its paragraph.

    Which requirements apply depends on the industry profile of the request: a
    medical procedure is judged against the rules for medical organisations, a
    construction one against the construction rules. Judging every draft against
    every industry would produce noise and teach a reader to ignore the section.

    The limit is the same for all of them: a marker word shows that a subject is
    addressed somewhere in the document. It does not show that it is addressed
    correctly, and the criterion is not a statement of compliance.
    """
    profile = source_request.industry_profile if source_request else "general"
    text = _instruction_text(instruction).lower()
    requirements = regulatory.requirements_for(profile)
    checks = {
        f"{item.label} ({item.citation()})": any(marker in text for marker in item.markers)
        for item in requirements
    }
    issue_labels = {
        f"{item.label} ({item.citation()})": f"{item.issue} — {regulatory.SOURCES[item.source].document}"
        for item in requirements
    }
    return _criterion("regulatory_structure", checks, issue_labels)


def _score_executability(instruction: WorkInstruction) -> CriterionScore:
    """Whether the document can be carried out at a workplace as written.

    The other criteria ask whether the instruction is complete, safe and on
    topic. None of them asks the question a foreman asks: can somebody pick this
    up and do it. A document can be complete and still unusable — nobody named
    to act, a value with no unit, a reference to "the relevant documentation"
    that names nothing.
    """
    steps = instruction.steps
    risky_steps = [step for step in steps if step.safety_note]
    text = _instruction_text(instruction).lower()
    checks = {
        # Not every step: a work instruction is written for one performer and
        # repeating the role in each line is bureaucratic noise. What matters is
        # that a step which can go wrong says who to turn to.
        "у рискованных шагов назван ответственный": (
            _share(
                _matches_any(f"{step.action} {step.safety_note or ''}", _ROLE_MARKERS)
                for step in risky_steps
            )
            if risky_steps
            else 1.0
        ),
        "у рискованных шагов есть способ проверки": (
            _share(bool(step.verification_method) for step in risky_steps) if risky_steps else 1.0
        ),
        # A generator cannot know the plant's document numbers, and saying so is
        # honest. What is not acceptable is saying it and leaving the reader to
        # discover it: an unnamed reference has to be carried into the list of
        # things to confirm locally.
        "отсылки к документам названы или вынесены на локальную проверку": (
            not any(marker in text for marker in _VAGUE_REFERENCES)
            or _mentions_document_verification(instruction)
        ),
        "числовые значения снабжены единицами измерения": _numbers_carry_units(instruction),
        "разделы не дублируют друг друга дословно": _distinct_share(
            [*instruction.control_points, *instruction.quality_checklist]
        )
        >= 0.9,
    }
    issue_labels = {
        "у рискованных шагов назван ответственный": (
            "в шагах с риском не сказано, к кому обращаться при отклонении"
        ),
        "у рискованных шагов есть способ проверки": (
            "у шагов с примечанием по безопасности нет способа проверки"
        ),
        "отсылки к документам названы или вынесены на локальную проверку": (
            "есть отсылки к неназванным документам, не вынесенные на локальную проверку"
        ),
        "числовые значения снабжены единицами измерения": (
            "часть числовых значений приведена без единиц измерения"
        ),
        "разделы не дублируют друг друга дословно": (
            "контрольные точки и чеклист качества повторяют друг друга"
        ),
    }
    return _criterion("executability", checks, issue_labels)


def _mentions_document_verification(instruction: WorkInstruction) -> bool:
    markers = ("документ", "регламент", "карт", "инструкц", "норматив")
    return any(
        any(marker in item.casefold() for marker in markers)
        for item in instruction.local_verification_required
    )


def _numbers_carry_units(instruction: WorkInstruction) -> float:
    """Share of numeric values followed by a unit.

    A torque of "45" is not a specification. Step numbers and enumerations are
    excluded by looking only at the sentence bodies where a parameter would sit.
    """
    fragments = [
        *(step.action for step in instruction.steps),
        *(step.expected_result for step in instruction.steps),
        *(step.verification_method or "" for step in instruction.steps),
        *instruction.control_points,
        *instruction.quality_checklist,
    ]
    values = 0
    with_units = 0
    for fragment in fragments:
        lowered = fragment.lower()
        for match in _NUMBER.finditer(lowered):
            values += 1
            tail = lowered[match.end() : match.end() + 12].strip()
            if any(tail.startswith(unit) for unit in _UNIT_MARKERS):
                with_units += 1
    if not values:
        return 1.0
    return with_units / values


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
        # Non-empty is guaranteed by the schema, so the question worth asking is
        # whether a blocker says anything an approver could act on.
        "есть блокеры утверждения": _is_substantive_list(instruction.workflow.approval_blockers),
        "есть следующие действия по внедрению": len(instruction.workflow.next_actions) >= 2,
    }
    return _criterion("implementation_readiness", checks)


def _criterion(
    name: str,
    checks: Mapping[str, bool | float],
    issue_labels: Mapping[str, str] | None = None,
) -> CriterionScore:
    """Свести набор проверок в оценку по критерию.

    Ключи `checks` — это формулировки, описывающие пройденную проверку, и они
    попадают в `strengths`. Часть проверок сформулирована через отрицание
    ("нет критических сигналов"): для них та же формулировка в списке проблем
    означала бы ровно противоположное тому, что произошло. Поэтому для таких
    проверок передаётся `issue_labels` — отдельный текст для случая провала.

    Значение проверки — либо `bool`, либо доля от 0 до 1. Доли нужны там, где
    измеряемое свойство непрерывно: «шаги связаны с задачей» — это не да/нет, а
    какая часть шагов связана. Пока такие проверки были булевыми, документ, уже
    не прошедший порог, нельзя было испортить дальше: одна лишняя нерелевантная
    операция и полностью посторонняя инструкция давали одинаковый балл.
    """
    overrides = issue_labels or {}
    passed: list[str] = []
    failed: list[str] = []
    values: list[float] = []
    for label, outcome in checks.items():
        value = _check_value(outcome)
        values.append(value)
        if value >= _CHECK_PASS_THRESHOLD:
            passed.append(label)
            continue
        text = overrides.get(label, label)
        if value > 0:
            text = f"{text} (выполнено на {round(value * 100)}%)"
        failed.append(text)
    score = round(100 * sum(values) / len(values)) if values else 0
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
    capped_by = _binding_safety_criterion(criteria)
    if capped_by is not None:
        recommendations.append(
            f"Итоговый балл ограничен критерием «{capped_by.label}» ({capped_by.score}): "
            "инструкция не может быть оценена выше собственной безопасности."
        )
    for criterion in criteria:
        if criterion.score < 80 and criterion.issues:
            recommendations.append(f"Усилить критерий «{criterion.label}»: {criterion.issues[0]}.")
    for item in missing:
        recommendations.append(f"Добавить раздел: {item}.")
    if not recommendations:
        recommendations.append("Инструкция структурно готова для демонстрационного сценария; следующий шаг — экспертная проверка на реальном процессе.")
    recommendations.append("Перед внедрением подтвердить актуальность источников, локальные допуски, режимы и ответственных лиц.")
    return recommendations[:8]


def _binding_safety_criterion(criteria: list[CriterionScore]) -> CriterionScore | None:
    """Return the safety criterion that holds the overall score down, if any."""
    safety_critical = [item for item in criteria if item.criterion in SAFETY_CRITICAL_CRITERIA]
    if not safety_critical:
        return None
    weakest = min(safety_critical, key=lambda item: item.score)
    if weakest.score >= SAFETY_FLOOR:
        return None
    weighted = sum(item.score * CRITERION_WEIGHTS.get(item.criterion, 1.0) for item in criteria)
    total_weight = sum(CRITERION_WEIGHTS.get(item.criterion, 1.0) for item in criteria)
    average = weighted / total_weight if total_weight else 0.0
    return weakest if weakest.score < average else None


def _verdict(score: int, safety_findings: list[SafetyFinding]) -> str:
    if safety_findings:
        return (
            "Структурная оценка завершена, но применение заблокировано safety-сигналами "
            "до проверки и исправления ответственным специалистом."
        )
    # The wording deliberately says "структура", never "качество". The score
    # counts whether required fields are present, filled with something
    # substantive and internally consistent. It cannot tell whether the
    # instruction is technically correct or safe for a specific machine — a
    # draft can be structurally complete and operationally wrong. Reading a high
    # number as "the instruction is right" is the single most likely way this
    # output misleads a technologist.
    if score >= 90:
        return (
            "Структура полная: обязательные разделы на месте и заполнены содержательно. "
            "Это оценка формы документа, а не его правильности — техническую верность "
            "подтверждает профильный специалист."
        )
    if score >= 75:
        return (
            "Структура в основном полная, есть отдельные пробелы в оформлении. "
            "Правильность содержания оценкой не проверяется."
        )
    if score >= 60:
        return (
            "Структура неполная: часть обязательных разделов отсутствует или заполнена формально. "
            "Требуется доработка до экспертной проверки."
        )
    return (
        "Структура непригодна: обязательных разделов не хватает настолько, "
        "что документ нельзя выносить на экспертную проверку."
    )


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


def _precise_values_are_covered(instruction: WorkInstruction) -> bool:
    """Require each precise value to be covered where it is stated.

    The previous form scanned the whole document: one occurrence of «подтвердить»
    anywhere marked every tolerance, torque and temperature in the text as
    handled. Coverage is now decided per step, and a step that states an exact
    value has to carry its own verification marker or name the parameter in the
    local-verification list.
    """
    local_verification = " ".join(instruction.local_verification_required).casefold()
    steps_with_values = [
        step for step in instruction.steps if _has_precise_value(f"{step.action} {step.expected_result}")
    ]
    if not steps_with_values:
        return not _has_precise_value(_instruction_text(instruction)) or _mentions_local_verification(
            local_verification
        )
    covered = 0
    for step in steps_with_values:
        own_text = " ".join(
            [step.action, step.expected_result, step.verification_method or "", step.safety_note or ""]
        )
        if _mentions_local_verification(own_text) or _keyword_overlap(step.action, local_verification) >= 0.3:
            covered += 1
    return covered == len(steps_with_values)


def _has_precise_value(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _PRECISE_VALUE_PATTERNS)


_PRECISE_VALUE_PATTERNS = (
    r"\b\d+([,.]\d+)?\s*(мм|см|м|кг|нм|н·м|об/мин|rpm|бар|мпа|°c|градус)",
    r"\b\d+([,.]\d+)?\s*(сек|мин|час)",
)


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
