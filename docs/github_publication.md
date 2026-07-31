# GitHub publication checklist

This checklist prepares Procedra for a strong but safe GitHub publication.

Evidence status: 2026-07-16. Publication remains **CONDITIONAL GO**. The local
engineering gate and S1 hostile-context regressions pass. The reproduced
provenance/evaluator false-confidence defect is locally remediated, but there is
still no real-data pilot, expert-labelled safety benchmark, production
deployment, or current Docker runtime validation.

## Publication goal

Position the repository as a serious AI/product engineering portfolio project:

- clear industrial problem;
- working product prototype;
- real technical depth;
- screenshots and reproducible demo artifacts;
- honest production-readiness boundaries;
- no invented traction, clients, revenue, or deployment claims;
- no secrets or runtime data committed.

## Suggested repository positioning

Recommended title:

```text
Procedra — Industrial Instruction AI
```

Possible repository names:

- `procedra`
- `procedra-industrial-ai`
- `industrial-instruction-ai`

Recommended short description:

```text
AI workflow prototype for generating review-ready industrial work instructions from tasks, documents, sources, and video context.
```

Suggested GitHub topics:

```text
ai, fastapi, industrial-ai, rag, manufacturing, pydantic, docker, computer-vision, workflow, audit-trail
```

## What to include

Recommended for the first public commit:

- `README.md`
- `app/`
- `tests/`
- `docs/`
- `examples/`
- `.github/workflows/`
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `.dockerignore`
- selected non-sensitive screenshots under `docs/assets/screenshots/`

## Current baseline scope

Use this matrix before staging the next public update.

| Area | Path-scope decision | Notes |
|---|---|---|
| Core application code, tests, Docker, CI, README, curated screenshots | Candidate public scope | Suitable for content-level review if the final checks below pass. |
| `docs/research/procedra_ssrn_working_paper.md`, `docs/research/procedra_ssrn_working_paper_pdf_ready.md`, `docs/research/procedra_ssrn_working_paper.pdf`, `docs/research/procedra_ssrn_submission_package.md`, `docs/research/procedra_ssrn_final_upload_checklist_for_alexander.md`, `docs/research/README.md` | Candidate research package | Keep the paper framed as a controlled local-demo prototype and software artifact. Do not add customer, production, compliance, or measured-impact claims. |
| `docs/procedra_demo_script.md`, `docs/procedra_outreach_messages.md`, `docs/procedra_pilot_for_customer.md`, `docs/partner_demo.md` | Candidate demo/pilot conversation package | Review content and use only approved non-confidential examples. |
| `docs/procedra_customer_pitch_deck_ru.md`, `docs/pilot_scope_draft.md`, `docs/commercial_contract_subject_draft.md` | Customer-review drafts | No party details are filled in, but these are business-development drafts rather than core GitHub narrative. Review deliberately before linking from public README, LinkedIn, or outreach. |
| `docs/Предметная_часть_пилотного_хоздоговора_Procedra.md` | Local/private | Contract-facing draft. Keep out of public GitHub unless Alexander explicitly approves publication after legal review. |
| `docs/research/audit/`, `docs/research/procedra_evidence_audit.md`, `docs/research/procedra_external_benchmark_audit.md`, `docs/research/procedra_materials_inventory.md`, `docs/research/ssrn_requirements_check.md`, other research working notes | Local/private | Useful working evidence, but not part of the first public research package. |
| `PROJECT_HANDOFF.md`, `reports/`, `generated/`, `uploads/`, `outputs/`, `output/`, `tmp/`, `.env.local`, `.venv/`, `__pycache__/`, `.DS_Store` | Local/private runtime or workspace state | Must remain ignored and absent from staged changes. |

“Candidate” means that the path is eligible for review; it does not certify the
file contents as public-safe. Before staging, separately scan candidate files
for secrets and credentials, then manually review PII, customer/process data,
third-party licensing, and unsupported product or research claims.

`make public-scope-audit` is only a path/staging-boundary gate. A pass does not
prove that candidate file contents are free of secrets, PII, confidential data,
third-party licensing issues, or unsupported claims.

Recommended to keep out of Git:

- `.env.local`
- real API keys or tokens;
- generated SQLite databases;
- uploads;
- local runtime volumes;
- `.venv/`;
- `__pycache__/`;
- `.DS_Store`;
- `PROJECT_HANDOFF.md` unless the repository is private and the internal
  continuation context is intentionally included;
- `outputs/`;
- `output/`;
- `tmp/`;
- `reports/` unless a specific public evidence subset is deliberately selected;
- bulky gate logs and generated report binaries;
- private partner materials;
- confidential customer documents or videos;
- bulky logs unless they are deliberate audit evidence.

## Safety checks before commit

Run:

```bash
git status --short
make public-scope-audit
git add --dry-run .
git check-ignore -v .env.local generated uploads outputs output tmp reports PROJECT_HANDOFF.md app/__pycache__/main.cpython-312.pyc app/.DS_Store
rg -l "OPENAI_API_KEY|API_ACCESS_TOKEN|sk-[A-Za-z0-9_-]+|BEGIN .*PRIVATE KEY|password|secret|token" \
  --glob '!.env.local' \
  --glob '!generated/**' \
  --glob '!uploads/**' \
  --glob '!.venv/**' \
  .
```

Then manually inspect any matches before staging.

## Recommended first commit message

```text
Initial public portfolio baseline for Procedra
```

## License decision

Before public release, choose one:

1. Private GitHub repository shared selectively with recruiters/partners.
2. Public repository with no open-source license yet, meaning source-visible but all rights reserved by default.
3. Public open-source repository with MIT or Apache-2.0 license.

Recommendation for a project intended to impress industrial partners: start private or public-without-open-source-license until commercial/IP plans are clearer. Add an explicit license later when the strategic direction is decided.

## Profile / pinned-repo framing

Suggested pinned-repo sentence:

```text
Built a local industrial AI workflow prototype that turns task descriptions,
documents, public sources, and video context into structured instruction drafts
with schema validation, structural quality evaluation, expert review, execution
evidence, and audit trail. Evaluation scores are not safety verdicts.
```

If writing in Russian:

```text
Разработал локальный AI-прототип для подготовки структурированных черновиков
производственных инструкций из описания задачи, документов, открытых источников
и видео-контекста: schema validation, структурная оценка качества, экспертное
согласование, чеклист исполнения и audit trail. Оценка не является safety verdict.
```

## Final pre-push gate

Recommended:

```bash
make smoke
make demo-eval
make partner-demo-pack
```

For a heavier baseline:

```bash
make compile
make lint
make typecheck
make test
make pip-check
make docker-config
```
