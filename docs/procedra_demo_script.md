# Procedra demo script

Status: public-safe demo script for portfolio, GitHub, LinkedIn, SSRN companion materials, and controlled partner conversations.

This script presents Procedra as a controlled local-demo prototype and research-informed software artifact. It does not claim production deployment, certified compliance, customer validation, paid pilots, revenue, measured productivity gains, or replacement of qualified expert review.

## Before recording or presenting

Run the local checks:

```bash
make smoke
make end-to-end
make demo-eval
make partner-demo-pack
```

Last verified 2026-08-02: smoke green with 423 tests, end-to-end 65/65 with no
failures under load, demo-eval 15/15 with an average structure score of 81,
partner pack built with 19 artifacts.

Start the application with `make run`. Since the deployment mode now defaults to
production, a bare `uvicorn app.main:app` refuses to start without configuration —
that is deliberate, and `make run` supplies the demo settings.

One thing to know while clicking: every `/api/` call counts against a ceiling of
300 requests per minute per client. Normal demo pace is nowhere near it, but a
long automated click-through can hit it.

**Video is deliberately not in this walkthrough.** Queued video work needs a
separate worker process, and frame-level analysis needs a configured model;
without one the pipeline returns fallback records rather than analysis. The
feature is implemented and covered for queueing, status and cancellation, but no
video has been processed end to end recently, so it is not demonstrated. Showing
an unverified feature is how a demo turns into a correction later. If asked, say
it exists, say it is not part of this recording, and move on.

To avoid opening on empty lists, fill the instance first:

```bash
python scripts/seed_demo_data.py
```

It signs in as a demo administrator, uploads one reference document and saves
three instructions across different profiles, then takes the first one through
expert review and records an execution run — the state a real user would have
after a week rather than after a fresh install. Everything it writes is
synthetic. Re-running adds a version rather than a duplicate.

Use only synthetic, public, or explicitly approved non-confidential materials. Do not show `.env`, `.env.local`, raw logs, runtime databases, uploaded private documents, private handoff files, customer materials, or local audit notes.

## Six-and-a-half-minute walkthrough

### 0:00-0:40 - Problem and boundary

Say:

> Procedra explores a practical industrial AI workflow: turning an operational task, technical context, approved documents, public references, and optional video context into a structured instruction draft. The point is not autonomous approval. The point is to create a review-ready draft with source context, local verification items, expert-review questions, version history, execution evidence, and audit traceability.

Show:

- README or the running web UI.
- Release status: controlled local demo / partner walkthrough prototype.

Do not say:

- production-ready;
- validated safety system;
- deployed at a customer;
- measured time savings.

### 0:40-1:30 - Input task

Use a stable manufacturing scenario:

```text
Подготовить рабочее место оператора перед запуском оборудования.
Участок: кузнечно-прессовый участок.
Оборудование: производственное оборудование участка.
Контекст: перед запуском проверить инструмент, ограждения, аварийную кнопку, чистоту зоны и готовность средств защиты.
```

Show:

- task fields;
- industry profile;
- technical context;
- source settings if visible.

Say:

> I intentionally use a narrow scenario. For real use, exact settings, permits, tolerances, responsible roles, and local rules must come from approved customer materials and expert review.

### 1:30-2:30 - Generated instruction

Show:

- generated instruction title and sections;
- PPE, hazards, prerequisites, steps, verification, control points, emergencies, mistakes, and workflow blockers.

Say:

> The useful part is not just text generation. The result is structured, validated, and easier to review than a free-form chat answer.

### 2:30-3:20 - Source context and uncertainty

Show:

- source tab;
- public/local source metadata;
- local verification items;
- expert-review questions.

Say:

> Procedra treats retrieved context as support for review, not as automatic factual validation. The system should surface what needs local confirmation instead of inventing missing industrial details.

### 3:20-4:00 - Structure score and export

Show:

- the structure score and its verdict text;
- recommendations or criterion-level scores;
- Markdown, JSON, and PDF export.

Say:

> This number measures the shape of the document — whether the required sections
> exist, whether they are filled with something substantive, whether declared
> hazards are addressed somewhere. It does not say the instruction is correct for
> this machine. A draft can be structurally complete and operationally wrong, and
> the wording on screen says "структура" rather than "качество" for that reason.

Do not say:

- "the instruction scored 95 out of 100" without the sentence above;
- "quality score";
- that the number reflects safety.

If asked how the criteria were validated, the honest answer is that they are
checked by a mutation harness (`make quality-discrimination`) which reports how
many checks never fail — currently a majority. There is no expert-labelled
benchmark behind the number.

### 4:00-5:00 - Version history and review workflow

Show:

- save version;
- reviewer decision;
- role-aware workflow state;
- audit or history view if available.

Say:

> The product is designed around accountability: who reviewed what, what changed, and what evidence exists around a draft.

### 5:00-5:50 - Operator checklist and execution evidence

Show:

- operator checklist;
- checked steps;
- execution notes;
- saved execution run.

Say:

> This is trial execution evidence for a controlled demo. It is not proof that the instruction is approved for real production use.

### 5:50-6:30 - What the system refused to assert

This is the section to spend time on. It is the part of the product that is
finished, tested, and hard to copy.

Show:

- the evidence claims list, every entry marked `unverified`;
- provenance types side by side: `user_claim` against `retrieved_unverified`;
- the local-verification list and the expert-review questions;
- approval blockers on the workflow.

Say:

> Nothing here can promote itself. A retrieved source cannot mark its own content
> as confirmed, and neither can the model — promotion requires an authenticated
> technologist, a reference to the evidence, and its hash, and the decision is
> appended to a hash-chained audit trail. The default answer of this system to
> "is this true" is "not verified", and that default is enforced by the schema
> rather than by a policy someone has to remember.

If you show one thing from Procedra, show this.

### 6:30-6:50 - Close with pilot scope

Say:

> The next practical step is one narrow pilot: one instruction family, one approved document set, named reviewers, and pre-agreed criteria for what is being evaluated. The pilot should separate what was tested from what was not tested.

Show:

- `docs/procedra_pilot_for_customer.md`;
- `docs/research/procedra_ssrn_working_paper.pdf` if the audience is research-oriented.

## 60-90 second recording

Use this for LinkedIn, GitHub, or a short portfolio clip.

### Shot plan

1. Product opening: show UI and one-sentence problem.
2. Input: show a narrow manufacturing task.
3. Result: show structured instruction sections.
4. Trust layer: show sources, structure score, and the claims marked unverified.
5. Workflow: show version/reviewer/checklist evidence.
6. Boundary: close with "review-ready draft, not autonomous approval."

### Voiceover

> Procedra is a controlled local-demo prototype for human-in-the-loop industrial AI. It turns a task, technical context, documents, and curated public references into a structured instruction draft. What the system adds is discipline: every factual claim carries a provenance type and stays unverified until an authenticated reviewer promotes it with evidence, and every decision lands in a hash-chained audit trail. It is not a production safety system and does not replace approved local procedures or qualified experts. The current goal is to support a narrow pilot conversation: one instruction family, approved non-confidential materials, named reviewers, and clear evaluation criteria.

## Demo evidence checklist

Before sharing a clip or meeting recording, confirm:

- no secrets, tokens, `.env` values, runtime paths, private logs, or customer-sensitive materials are visible;
- no raw `reports/`, generated databases, uploads, private handoff files, or local audit notes are shown;
- screenshots and video frames are synthetic, public, or explicitly approved;
- no unsupported claims are made about production readiness, compliance, customer deployment, paid pilots, revenue, or quantified impact;
- the demo states that human review is required before any real-world operational use.

## Follow-up questions

Use these after the demo:

- Which instruction family is painful enough to test first?
- Which approved documents can be used safely?
- Who must review a draft before any operational use?
- What does a useful pilot output look like: PDF, Markdown, JSON, source list, expert questions, run summary, or all of these?
- Which metric should be measured if the pilot moves beyond a walkthrough?
- What data must stay out of the pilot environment?
