from app.schemas.instruction import StepFrameLink, WorkInstruction


def _extend_list(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend(["", f"## {title}"])
    lines.extend(f"- {item}" for item in items or ["Не указано"])


def _format_time(seconds: float) -> str:
    total_seconds = int(round(seconds))
    minutes = total_seconds // 60
    remainder = total_seconds % 60
    return f"{minutes:02d}:{remainder:02d}"


def _evidence_claim_items(instruction: WorkInstruction) -> list[str]:
    items = []
    for claim in instruction.evidence_claims:
        metadata = "; ".join(
            [
                claim.claim_id or "claim_id отсутствует",
                claim.provenance,
                claim.validation_status,
                f"source={claim.source_id or 'не указан'}",
            ]
        )
        item = f"[{metadata}] {claim.text}"
        if claim.validation_record:
            item += (
                " | validated by "
                f"{claim.validation_record.reviewer_name} ({claim.validation_record.reviewer_role}); "
                f"evidence={claim.validation_record.evidence_reference}"
            )
        items.append(item)
    return items


def render_instruction_markdown(
    instruction: WorkInstruction,
    step_frame_links: list[StepFrameLink] | None = None,
) -> str:
    links_by_step = {link.step_number: link for link in step_frame_links or []}
    lines = [
        f"# {instruction.title}",
        "",
        "## Назначение",
        instruction.purpose,
        "",
        "## Область применения",
        instruction.scope,
        "",
        "## Паспорт инструкции",
        f"- Участок: {instruction.department or 'Не указано'}",
        f"- Оборудование: {instruction.equipment or 'Не указано'}",
        f"- Уровень пользователя: {instruction.operator_level}",
        f"- Статус: {instruction.workflow.status_label}",
    ]
    _extend_list(lines, "Роли для согласования", instruction.workflow.required_review_roles)
    _extend_list(lines, "Блокеры перед утверждением", instruction.workflow.approval_blockers)
    _extend_list(lines, "Следующие действия по внедрению", instruction.workflow.next_actions)
    _extend_list(
        lines,
        "Матрица ответственности",
        [
            "Оператор выполняет действия только в пределах допуска и фиксирует отклонения.",
            "Мастер смены подтверждает применимость инструкции к конкретному участку и оборудованию.",
            "Инженер/технолог уточняет режимы, допуски и локальные требования, отсутствующие во входных данных.",
        ],
    )
    _extend_list(lines, "Утверждения из входных данных", instruction.observed_facts)
    _extend_list(lines, "Происхождение и статус утверждений", _evidence_claim_items(instruction))
    _extend_list(lines, "Что требуется проверить локально", instruction.local_verification_required)
    _extend_list(lines, "Вопросы для экспертной проверки", instruction.expert_review_questions)
    _extend_list(lines, "Средства индивидуальной защиты", instruction.required_ppe)
    _extend_list(lines, "Инструменты и документы", instruction.required_tools)
    _extend_list(lines, "Требования безопасности", instruction.safety_requirements)
    _extend_list(lines, "Опасные зоны", instruction.hazard_zones)
    _extend_list(lines, "Предварительные условия", instruction.prerequisites)

    lines.extend(["", "## Порядок выполнения"])
    for step in instruction.steps:
        link = links_by_step.get(step.number)
        lines.append(f"{step.number}. {step.action}")
        lines.append(f"   Ожидаемый результат: {step.expected_result}")
        if step.safety_note:
            lines.append(f"   Безопасность: {step.safety_note}")
        if step.verification_method:
            lines.append(f"   Проверка: {step.verification_method}")
        if step.common_mistakes:
            lines.append(f"   Типовые ошибки: {', '.join(step.common_mistakes)}")
        if link:
            lines.append(
                "   Видео: "
                f"{_format_time(link.timestamp_seconds)}, кадр {link.frame_index}, "
                f"уверенность {link.confidence:.2f}"
            )
            lines.append(f"   Причина связи: {link.reason}")

    _extend_list(
        lines,
        "Критерии приемки результата",
        [
            "Все обязательные контрольные точки выполнены и подтверждены ответственным лицом.",
            "Рабочее место и оборудование находятся в безопасном, определенном состоянии.",
            "Отклонения, замечания и ограничения зафиксированы в принятой на участке форме.",
            *instruction.control_points,
        ],
    )
    _extend_list(lines, "Контрольные точки", instruction.control_points)
    _extend_list(lines, "Чеклист качества", instruction.quality_checklist)
    _extend_list(lines, "Действия при нештатной ситуации", instruction.emergency_actions)
    _extend_list(lines, "Типовые ошибки", instruction.common_mistakes)
    _extend_list(
        lines,
        "Ограничения и проверка перед внедрением",
        [
            "Документ является AI-черновиком и не заменяет утвержденные инструкции предприятия.",
            "Точные режимы, нормы времени, допуски и ссылки на стандарты должны быть подтверждены локальной документацией.",
            "Перед применением на производстве инструкцию должен проверить ответственный специалист по технологии и охране труда.",
        ],
    )
    return "\n".join(lines).strip() + "\n"
