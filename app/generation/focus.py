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

    # The equipment stays in the title. A shop with four lathes cannot tell which
    # machine "Инструкция: Техническое обслуживание станка" covers, and the model
    # is what a person searches the folder by. The focus layer used to drop it.
    equipment = _single_line(request.equipment or "")
    title = f"Инструкция: {_truncate(focus_phrase, 90)}"
    if equipment and equipment.casefold() not in title.casefold():
        title = _truncate(f"{title} ({equipment})", 140)
    focused.title = title
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

    # A "most steps do not relate to the task" question used to be raised here,
    # from the word overlap between each step's action and the request. It was
    # removed rather than tuned: the overlap ran on a hand-written stemmer, and
    # the stemmer does not survive Russian cases. "Рабочее место" in a request
    # became {рабоче, место} while "рабочего места" in a step became {рабочего},
    # so a step describing exactly what was asked for scored zero and the draft
    # was reported to the reviewer as off-topic. Raising the threshold would not
    # help — the blindness is to grammar, not to the count — and doing it
    # properly needs a morphological analyser, which is a dependency this check
    # does not earn. A draft that drifted into another job is already caught by
    # the profile-mismatch note in the evaluator, which reads the request rather
    # than guessing at word forms.
    return focused


def _focus_phrase(request: InstructionRequest) -> str:
    return _single_line(request.operation_name or request.task)


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
