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

    # A step that shares no words with the request is worth flagging — to the
    # reviewer, not to the person doing the work. Appending "perform this step
    # only within the task ..." to the action put a machine's note in the middle
    # of an instruction someone reads at a machine, and it did something worse:
    # the appended sentence contained the words of the request, so the very check
    # that measures how many steps relate to the task was reading text the focus
    # layer had just inserted. The signal now goes where it belongs.
    focus_tokens = _focus_tokens(request)
    unrelated = [
        step.number
        for step in focused.steps
        if focus_tokens and _overlap(step.action, focus_tokens) == 0
    ]
    # Word overlap is a weak measure of whether a step belongs to a task:
    # "hang the do-not-switch-on sign" shares nothing with "machine maintenance"
    # and is plainly part of it. Naming such steps to a reviewer would send them
    # after the wrong ones. The question is raised only when most of the document
    # fails to relate, which is the case the focus layer exists for — a draft
    # that drifted into another job.
    if unrelated and len(unrelated) > len(focused.steps) / 2:
        _prepend_unique(
            focused.expert_review_questions,
            f"Большая часть шагов не связана с задачей «{_truncate(focus_phrase, 80)}» — "
            "проверить, не описывает ли инструкция другую операцию.",
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
