from app.generation.industry_profiles import profile_guardrails, profile_label
from app.schemas.instruction import InstructionRequest, WorkInstruction


MIN_SAFETY_REQUIREMENTS = 4
MIN_CONTROL_POINTS = 4
MIN_QUALITY_ITEMS = 4
MIN_EMERGENCY_ACTIONS = 4
MIN_COMMON_MISTAKES = 3
MIN_LOCAL_CHECKS = 3
MIN_EXPERT_QUESTIONS = 3


def improve_instruction_quality(instruction: WorkInstruction, request: InstructionRequest) -> WorkInstruction:
    improved = instruction.model_copy(deep=True)

    _improve_steps(improved)
    _extend_unique(
        improved.required_tools,
        [
            "Актуальная локальная инструкция, технологическая карта или регламент участка",
            "Форма фиксации результата, отклонений и допуска к продолжению работы",
        ],
        2,
    )
    _extend_unique(
        improved.safety_requirements,
        [
            "Не начинать и не продолжать операцию при неясном состоянии оборудования, зоны работ или полномочий исполнителя.",
            "Остановить работу и сообщить ответственному лицу при повреждении защиты, блокировке доступа к аварийной остановке или посторонних предметах в опасной зоне.",
            "Проверять требования безопасности по актуальной локальной документации перед применением AI-черновика.",
            *_profile_safety_items(request),
        ],
        MIN_SAFETY_REQUIREMENTS,
    )
    _extend_unique(
        improved.control_points,
        [
            "Ответственный мастер, наставник или профильный специалист подтвердил применимость инструкции к месту работ.",
            "Опасные зоны, СИЗ, документация и аварийные действия проверены до начала выполнения.",
            "Неподтвержденные режимы, допуски, роли и формы записи вынесены на локальную проверку.",
            "Итоговое состояние, отклонения и разрешение на продолжение работы зафиксированы в принятой форме.",
        ],
        MIN_CONTROL_POINTS,
    )
    _extend_unique(
        improved.quality_checklist,
        [
            "Все шаги имеют проверяемый ожидаемый результат.",
            "Критические риски и запреты понятны исполнителю выбранного уровня подготовки.",
            "Все предположения отделены от подтвержденных фактов и вынесены на локальную проверку.",
            "Инструкция проверена ответственным лицом перед применением на реальном объекте.",
        ],
        MIN_QUALITY_ITEMS,
    )
    _extend_unique(
        improved.emergency_actions,
        [
            "Немедленно прекратить операцию при угрозе жизни, здоровью, оборудованию или объекту.",
            "Сообщить мастеру, руководителю работ, диспетчеру или иному ответственному лицу по локальному порядку.",
            "Не возобновлять работу до устранения причины, фиксации события и подтверждения допуска.",
            "Сохранить место события в безопасном состоянии для последующей проверки, если это не создает дополнительный риск.",
        ],
        MIN_EMERGENCY_ACTIONS,
    )
    _extend_unique(
        improved.common_mistakes,
        [
            "Применение AI-черновика без проверки актуальных локальных документов.",
            "Продолжение работы при сомнительном состоянии оборудования, зоны работ или исходных данных.",
            "Отсутствие записи о результате, отклонениях или разрешении на продолжение работы.",
        ],
        MIN_COMMON_MISTAKES,
    )
    _extend_unique(
        improved.observed_facts,
        _observed_fact_items(request),
        3,
    )
    _extend_unique(
        improved.local_verification_required,
        [
            "Подтвердить актуальную редакцию локальных инструкций, регламентов, технологических карт и применимых нормативных требований.",
            "Подтвердить точные режимы, допуски, роли, границы работ, СИЗ и форму фиксации результата.",
            "Проверить, какие действия разрешены исполнителю выбранного уровня подготовки, а какие требуют допуска или присутствия наставника.",
            *_profile_local_checks(request),
        ],
        MIN_LOCAL_CHECKS,
    )
    _extend_unique(
        improved.expert_review_questions,
        [
            "Какие локальные документы и ответственные лица должны утвердить инструкцию перед внедрением?",
            "Какие условия требуют немедленной остановки работ и эскалации?",
            "Какие параметры, допуски, СИЗ, роли и формы записи нельзя определять без проверки на месте?",
        ],
        MIN_EXPERT_QUESTIONS,
    )
    return improved


def _improve_steps(instruction: WorkInstruction) -> None:
    for step in instruction.steps:
        if not step.safety_note:
            step.safety_note = "Не выполнять шаг при неясном состоянии, опасном отклонении или отсутствии подтвержденного допуска."
        if not step.verification_method:
            step.verification_method = "Проверить результат по локальной инструкции, чеклисту участка или подтверждению ответственного лица."
        _extend_unique(
            step.common_mistakes,
            [
                "Выполнение шага по памяти без сверки с актуальной документацией.",
                "Переход к следующему шагу без проверки результата.",
            ],
            1,
        )


def _observed_fact_items(request: InstructionRequest) -> list[str]:
    facts = [
        f"Отраслевой профиль запроса: {profile_label(request.industry_profile)}.",
        f"Тип инструкции во входных данных: {request.instruction_type}.",
        f"Уровень пользователя во входных данных: {request.user_level}.",
    ]
    if request.department:
        facts.append(f"Участок указан во входных данных: {request.department}.")
    if request.equipment:
        facts.append(f"Оборудование указано во входных данных: {request.equipment}.")
    if request.operation_name:
        facts.append(f"Название операции указано во входных данных: {request.operation_name}.")
    if request.technical_context:
        facts.append(
            "Технический контекст был предоставлен как непроверенный источник и требует локального подтверждения."
        )
    return facts


def _profile_safety_items(request: InstructionRequest) -> list[str]:
    return [
        f"Профильное требование для проверки безопасности: {item}"
        for item in profile_guardrails(request.industry_profile)[:2]
    ]


def _profile_local_checks(request: InstructionRequest) -> list[str]:
    return [
        f"Подтвердить применимость профильного требования: {item}"
        for item in profile_guardrails(request.industry_profile)[:2]
    ]


def _extend_unique(target: list[str], candidates: list[str], minimum: int) -> None:
    seen = {item.casefold() for item in target}
    for candidate in candidates:
        cleaned = " ".join(candidate.split())
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        target.append(cleaned)
        seen.add(key)
        if len(target) >= minimum:
            break
