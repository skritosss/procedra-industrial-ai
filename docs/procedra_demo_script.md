# Procedra demo script

Status: public-safe recording script. Procedra is presented as a controlled local
demo and a research-informed software artifact. Nothing here claims production
deployment, certified compliance, customer validation, paid pilots, revenue,
measured productivity gains, or a replacement for qualified expert review.

The narration is Russian. The audience is a mid-size Russian machine-building or
metalworking plant, and the first ten seconds decide whether the rest is heard.

Two cuts come out of one recording session:

| Cut | Length | Where it goes | What it has to do |
|---|---|---|---|
| Short | ~100 s | First paragraph of a cold letter | Get the letter read |
| Full | ~7 min | Sent after a reply | Replace the first call |

The short cut is not an abridged version of the long one. It has its own
voiceover and its own pace, and it is recorded separately.

## Before recording

```bash
make smoke
python scripts/seed_demo_data.py   # with the app already running
make run
```

Verified 2026-09-02: 459 tests, ruff, mypy, static-asset smoke, both public-scope
audits green; `make demo-eval` 15/15 with an average structure score of 94.2;
`make quality-discrimination` 45 mutations, 0 undetected, 1 blind check of 80.

Seeding matters. A recording that opens on empty lists spends its first minute
proving the product works at all. `seed_demo_data.py` leaves three saved
instructions across profiles, one already in expert review, an execution run, and
an uploaded reference document — the state of someone in their second week.

Interface language RU. Light theme. Browser zoom 125-150 %: half the audience
opens the link on a phone. Close other tabs, mail, and messengers. Never on
screen: `.env`, logs, `reports/`, runtime databases, private handoff files,
uploaded personal documents, a terminal showing the machine name.

**Video ingest is not demonstrated.** Queued video needs a separate worker and a
configured model, and no clip has been processed end to end recently. If asked:
the feature exists, it is not part of this recording, move on.

Read at roughly 135 words per minute. Faster reads as a sales pitch, and this
audience hears a sales pitch as a reason to stop listening.

## Screens verified 2026-09-02

Every screen below was generated and read in a browser against the scenario in
this script, not assumed:

- passport, approval roles, approval blockers (6 entries), next actions;
- PPE, responsibility matrix, observed facts, claim provenance (8 claims, every
  one `unverified`), local verification list (9), expert-review questions (9);
- tools, safety requirements (9), hazard zones (3), prerequisites (6);
- five steps, each with expected result, verification method, common mistakes,
  and a safety note;
- acceptance criteria, control points (13), quality checklist (7), emergency
  actions (6), common mistakes (5), implementation limits;
- the checks tab: structure score 94, risk level, the wording that separates
  structure from correctness, and `Сверено с документами` listing seven
  documents;
- Markdown, JSON, and PDF export.

Verification found and removed one defect on the way: the expert-review list
opened with «Большая часть шагов не связана с задачей …» on a draft that was
entirely on topic — a false positive from word overlap over a hand-written
stemmer that does not survive Russian cases. Every block listed above is safe to
film as it stands.

## Full cut, 7 minutes

### 0:00-0:30 — The problem, not the product

Screen: the empty application, cursor still.

> Инструкцию по эксплуатации или по охране труда на участке пишет технолог. На
> один документ уходит от нескольких дней до недели: собрать требования, свести
> с правилами, оформить по структуре, согласовать. Поменялось оборудование или
> вышла новая редакция правил — цикл повторяется. При проверке выясняется, что в
> половине документов не хватает обязательных разделов, и это не халатность, а
> объём.
>
> Procedra не заменяет технолога. Она снимает с него черновик.

### 0:30-1:20 — The input

Screen: fill the fields one at a time, unhurried.

```text
Задача: Подготовить рабочее место оператора перед запуском кривошипного
        горячештамповочного пресса
Название операции: Подготовка пресса к запуску
Участок: Кузнечно-прессовый участок
Оборудование: Кривошипный горячештамповочный пресс
Профиль: Производство
Тип: Подготовка рабочего места
Контекст: Перед запуском проверить защитные ограждения, аварийную кнопку,
исправность инструмента, чистоту рабочей зоны и наличие средств защиты.
```

> Ввод — это то, что технолог и так держит в голове: задача, участок,
> оборудование, отрасль и короткий контекст. Отдельно можно приложить
> утверждённые документы предприятия — стандарты, регламенты, паспорта
> оборудования, — и система будет опираться на них, а не на общие сведения из
> интернета.
>
> Сценарий здесь намеренно узкий. Точные режимы, допуски, наряды-допуски и
> распределение ответственности берутся из документов предприятия и проходят
> проверку специалистом. Система их не выдумывает — и дальше я покажу, как
> именно она отказывается это делать.

Press generate. The result appears almost at once; do not remark on the speed, it
pulls attention away from what matters.

### 1:20-2:20 — The draft

Screen: slow scroll. Rest on СИЗ, Опасные зоны, Порядок выполнения, Контрольные
точки, Типовые ошибки, Действия при нештатной ситуации.

> Это не текст в чате. Это документ со структурой: назначение, средства защиты,
> опасные зоны, предварительные условия, порядок выполнения, проверка,
> контрольные точки, типовые ошибки, действия при нештатной ситуации.
>
> Обратите внимание на два раздела, которых в обычной генерации не бывает.
> Контрольные точки — что именно проверить и по какому признаку понять, что шаг
> выполнен правильно. Типовые ошибки — то, на чём чаще всего ошибается новый
> оператор.
>
> Ценность не в том, что текст сгенерирован. Ценность в том, что его можно
> проверять по частям. Технолог не перечитывает документ целиком — он смотрит
> раздел за разделом и правит те, где ошиблись.

### 2:20-3:10 — What the checks rest on

Screen: the checks tab, the `Сверено с документами` line with its list.

> Проверка структуры опирается не на представления разработчика о том, как
> должна выглядеть инструкция. Обязательные разделы сверяются с приказом
> Минтруда России номер 772н от 29 октября 2021 года — это документ, который
> устанавливает требования к содержанию инструкций по охране труда.
>
> Для производственного профиля к нему добавляются правила по охране труда при
> размещении, монтаже, обслуживании и ремонте технологического оборудования,
> правила при работе с инструментом и приспособлениями, ГОСТ по безопасности
> производственного оборудования и производственных процессов, ГОСТ по
> оформлению технологической документации и порядок обучения по охране труда.
>
> Отдельно скажу то, что обычно не говорят. ГОСТ 12.0.004 по организации
> обучения система сознательно не использует: его действие приостановлено до
> сентября 2026 года. Сослаться на него было бы легко и выглядело бы солиднее.
> Это была бы ошибка, и она всплыла бы у вас на проверке, а не у нас.

This is the block after which a safety engineer starts listening differently. Do
not shorten it.

### 3:10-3:50 — The structure score

Screen: the score, then the expanded criteria list.

> Балл структуры. Двенадцать критериев: полнота, понятность, соответствие
> входным данным, фокус на задаче, безопасность, логическая последовательность,
> пригодность для обучения, опора на источники, контроль отраслевых рисков,
> готовность к внедрению, исполнимость на месте, соответствие обязательной
> структуре.
>
> Здесь важна оговорка, и она написана прямо в интерфейсе. Это балл структуры, а
> не балл качества. Он говорит, что документ полон и оформлен как положено. Он
> не говорит, что документ правильный для вашего конкретного пресса. Инструкция
> может быть структурно безупречной и при этом операционно неверной.
>
> Поэтому у непроверенного черновика есть потолок: сто баллов он получить не
> может в принципе.

Never say "quality score", never quote the number without the caveat, never
suggest it reflects safety.

### 3:50-4:30 — What checked the checks

Screen: a terminal running `make quality-discrimination`, ending on the summary
line.

> Любой продукт с ИИ показывает вам свою оценку качества. Вопрос, который стоит
> задавать: а чем проверяли саму оценку.
>
> У нас для этого есть стенд. Он берёт правильную инструкцию и намеренно портит
> её сорока пятью способами: убирает средства защиты, ломает порядок шагов,
> вычищает упоминания опасностей, подменяет отрасль в запросе. И смотрит,
> заметит ли оценка каждое повреждение.
>
> Сейчас незамеченных повреждений — ноль. Одна проверка из восьмидесяти не
> различает ничего, и она показана в отчёте открыто, а не убрана.
>
> Честная граница: это проверка на устойчивость, а не на согласие с экспертом.
> Размеченного специалистами эталона у нас нет — его можно получить только на
> пилоте, у вас.

### 4:30-5:10 — What the system refused to assert

Screen: `Происхождение и статус утверждений`, one or two rows large, then
`Что требуется проверить локально` and `Вопросы для экспертной проверки`.

> Это главное, что есть в продукте, и это единственный экран, на котором я
> задержусь.
>
> Каждое утверждение в документе несёт метку происхождения и статус. Пришло из
> ваших входных данных, найдено в источнике, сгенерировано — и рядом статус. По
> умолчанию статус один: не проверено.
>
> Источник не может подтвердить сам себя. Модель не может подтвердить сама себя.
> Чтобы перевести утверждение в подтверждённые, нужен аутентифицированный
> технолог, ссылка на доказательство и его хеш, и это решение уходит в
> аудит-цепочку, где запись нельзя изменить задним числом.
>
> Отдельным списком — что требуется проверить на месте, и вопросы, на которые
> должен ответить эксперт. Система не делает вид, что знает то, чего не знает.

The provenance rows are a machine format and look technical. Show one or two
large and move on; do not walk through the fields.

### 5:10-5:50 — Review and versions

Screen: save version, `Блокеры перед утверждением`, a reviewer decision, history.

> Дальше документ живёт по обычному заводскому порядку. Роли — мастер участка,
> технолог, охрана труда, качество. У версии есть блокеры: пока они не закрыты,
> утвердить её нельзя.
>
> Проверяющий фиксирует решение, оно привязано к конкретной версии и к
> конкретному человеку. Через полгода на вопрос «кто это утверждал и что именно
> он видел» есть ответ, а не устная реконструкция.

### 5:50-6:30 — Execution and export

Screen: operator checklist, checked steps, a note. Then export PDF and scroll the
opened file.

> Оператор работает по чек-листу и отмечает шаги. Остаются заметки и запись
> прогона — что фактически выполнялось, а не что было написано.
>
> Выгрузка — PDF, Markdown или JSON. PDF идёт на участок в том виде, в каком его
> подшивают. JSON — если у вас есть система документооборота и документ должен
> попасть туда.

### 6:30-7:00 — Close on a pilot

Screen: the title page of the exported PDF.

> Практический следующий шаг — один узкий пилот. Одно семейство инструкций,
> утверждённый комплект документов, названные проверяющие и заранее
> согласованные критерии: что мы считаем результатом, а что не проверяли.
>
> И то, о чём спросит служба безопасности. Модель может стоять внутри вашего
> контура — на вашем сервере, без выхода наружу. Это не обещание в презентации:
> запрет на внешние вызовы включается настройкой и проверяется в трёх слоях, а
> если конфигурация нарушена, система откажется работать по модели, а не тихо
> отправит данные наружу.
>
> Готов обсудить, с какого семейства инструкций начинать.

## Short cut, ~100 seconds

Screen only, no face. Separate voiceover — this does not cut down from the long
version.

**0:00-0:12** — the form being filled.

> Инструкция по охране труда на участок пишется днями. Procedra делает черновик,
> который остаётся проверить.

**0:12-0:35** — scrolling the finished document.

> Не текст в чате, а документ со структурой: средства защиты, опасные зоны,
> порядок выполнения, контрольные точки, типовые ошибки, действия при нештатной
> ситуации.

**0:35-0:52** — the `Сверено с документами` block.

> Обязательные разделы сверяются с приказом Минтруда 772н и отраслевыми
> правилами по охране труда. Не с представлениями разработчика о том, как это
> должно выглядеть.

**0:52-1:20** — the provenance section.

> Каждое утверждение помечено: откуда пришло и проверено ли оно. По умолчанию —
> не проверено. Ни источник, ни модель не могут подтвердить сами себя: для этого
> нужен технолог, ссылка на доказательство и запись в аудит-цепочке.

**1:20-1:40** — PDF export, the finished document.

> Черновик для проверки, а не автоматическое утверждение. Работает внутри
> контура предприятия, без выхода данных наружу.

## Never say

Production-ready. Validated safety system. Deployed at a customer. Complies with
GOST — the system *checks against* documents, a person establishes compliance.
Saves N hours — no measured figure exists. Any customer, pilot, or percentage
that does not exist.

Asked about deployments, the answer is that there have been no pilots yet and one
is being sought. That answer is fine. An attempt to talk around it is audible.

## Demo evidence checklist

Before sharing a clip or a meeting recording, confirm:

- no secrets, tokens, `.env` values, runtime paths, private logs, or
  customer-sensitive material is visible;
- no `reports/`, generated databases, uploads, private handoff files, or local
  audit notes are on screen;
- every frame is synthetic, public, or explicitly approved;
- no claim is made about production readiness, compliance, customer deployment,
  paid pilots, revenue, or quantified impact;
- the recording states that human review is required before any operational use.

## Follow-up questions

- Which instruction family is painful enough to test first?
- Which approved documents can be used safely?
- Who must review a draft before any operational use?
- What does a useful pilot output look like: PDF, Markdown, JSON, source list,
  expert questions, run summary, or all of these?
- Which metric should be measured if the pilot moves beyond a walkthrough?
- What data must stay out of the pilot environment?
