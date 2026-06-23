import re

from app.schemas.instruction import InstructionRequest, WorkInstruction


FOCUS_NOTE = (
    "Граница инструкции: выполнять только действия, необходимые для указанной задачи; "
    "смежные операции не включать, кроме обязательных проверок безопасности и локальной применимости."
)


def focus_instruction_on_request(instruction: WorkInstruction, request: InstructionRequest) -> WorkInstruction:
    focused = instruction.model_copy(deep=True)
    focus_phrase = _focus_phrase(request)
    if not focus_phrase:
        return focused

    focused.title = f"Инструкция: {_truncate(focus_phrase, 90)}"
    focused.purpose = _prepend_once(
        focused.purpose,
        f"Решить конкретную задачу пользователя: {focus_phrase}.",
    )
    focused.scope = _append_once(focused.scope, FOCUS_NOTE)

    _prepend_unique(
        focused.control_points,
        f"Фокус задачи подтвержден: инструкция применима именно к запросу «{_truncate(focus_phrase, 140)}».",
    )
    _prepend_unique(
        focused.quality_checklist,
        "Инструкция не расширяет задачу за пределы пользовательского запроса, кроме обязательных мер безопасности.",
    )
    _prepend_unique(
        focused.local_verification_required,
        "Проверить, что локальная доработка не добавляет смежные операции, не относящиеся к исходной задаче.",
    )
    _prepend_unique(
        focused.expert_review_questions,
        "Не добавлены ли в инструкцию действия, которые выходят за пределы исходного запроса пользователя?",
    )

    focus_tokens = _focus_tokens(request)
    for step in focused.steps:
        if focus_tokens and _overlap(step.action, focus_tokens) == 0:
            step.action = _append_once(
                step.action,
                f"Выполнять этот шаг только в рамках задачи: {_truncate(focus_phrase, 100)}.",
            )
    return focused


def _focus_phrase(request: InstructionRequest) -> str:
    return _single_line(request.operation_name or request.task)


def _focus_tokens(request: InstructionRequest) -> set[str]:
    return _tokens(
        " ".join(
            part
            for part in [
                request.task,
                request.operation_name or "",
                request.equipment or "",
                request.department or "",
            ]
            if part
        )
    )


def _prepend_once(value: str, prefix: str) -> str:
    if prefix.lower() in value.lower():
        return value
    return f"{prefix} {value}".strip()


def _append_once(value: str, suffix: str) -> str:
    if suffix.lower() in value.lower():
        return value
    return f"{value.rstrip()} {suffix}".strip()


def _prepend_unique(items: list[str], item: str) -> None:
    key = item.casefold()
    if key in {existing.casefold() for existing in items}:
        return
    items.insert(0, item)


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, limit: int) -> str:
    compact = _single_line(value)
    if len(compact) <= limit:
        return compact
    return compact[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,.;:") + "..."


def _overlap(text: str, focus_tokens: set[str]) -> int:
    return len(_tokens(text) & focus_tokens)


def _tokens(text: str) -> set[str]:
    stopwords = {
        "инструкц",
        "провер",
        "подготов",
        "выполн",
        "операц",
        "задач",
        "пользовател",
        "работ",
        "рабоч",
        "мест",
        "оборудован",
        "безопасн",
    }
    tokens = set()
    for raw in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text.lower().replace("ё", "е")):
        token = _normalize(raw)
        if len(token) >= 4 and token not in stopwords:
            tokens.add(token)
    return tokens


def _normalize(token: str) -> str:
    replacements = {
        "аварийная": "аварийн",
        "аварийной": "аварийн",
        "аварийную": "аварийн",
        "кнопка": "кнопк",
        "кнопки": "кнопк",
        "кнопку": "кнопк",
        "ограждение": "огражд",
        "ограждения": "огражд",
        "ограждений": "огражд",
        "станка": "станок",
        "станке": "станок",
    }
    if token in replacements:
        return replacements[token]
    endings = ("иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ить", "ать", "ией", "ия", "ий", "ый", "ой", "ые", "ая", "ое", "ов", "ев", "ам", "ям", "ах", "ях", "ом", "ем", "а", "я", "ы", "и", "у", "ю", "е")
    for ending in endings:
        if token.endswith(ending) and len(token) - len(ending) >= 4:
            return token[: -len(ending)]
    return token
