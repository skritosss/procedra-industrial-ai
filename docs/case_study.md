# Procedra — portfolio case study

Status: public-facing draft for GitHub / portfolio packaging.
This case study describes what is implemented in the repository and avoids unverified customer, revenue, traction, or deployment claims.

## One-line summary

Procedra is an AI workflow prototype for turning industrial task descriptions, technical context, documents, and video-derived context into review-ready manufacturing instructions with source grounding, quality evaluation, expert review, execution evidence, and audit traceability.

## Problem

Manufacturing and industrial teams need clear operating instructions, but creating and updating them manually is slow and fragile:

- critical knowledge often lives with experienced engineers, technologists, supervisors, or safety specialists;
- instructions can vary by author and site;
- updates are difficult when equipment, tooling, regulations, or local procedures change;
- it is hard to prove which sources were used, who reviewed a draft, and whether a trial execution happened.

## Product hypothesis

An AI system can reduce the manual effort of preparing first drafts if it is constrained by:

- structured output schemas;
- retrieval over approved materials;
- explicit uncertainty and expert-review blocks;
- deterministic evaluation;
- human approval workflow;
- audit and execution traceability.

The system should not pretend to replace a technologist, safety specialist, or approved local procedure.

## What was built

Confirmed in the repository:

- FastAPI web application with a bilingual RU/EN interface.
- Structured industrial instruction generation in JSON, Markdown, and PDF.
- Deterministic fallback when OpenAI is disabled or unavailable.
- Pydantic validation and stable API error envelopes.
- Deterministic quality evaluation and improvement passes.
- Local/uploaded/public-source retrieval.
- Video metadata, transcript/context, keyframe, and semantic-stage processing.
- SQLite-backed accounts, sessions, roles, organizations, projects, invitations, audit events, instruction versions, and execution runs.
- Role-gated review workflow and operator checklist mode.
- Rate limiting, security headers, readiness, metrics, request IDs, and redacted structured JSON logs.
- Docker Compose local demo, GitHub Actions configuration, tests, Ruff, mypy, compile, and reproducible demo packs.

## Technical decisions

### 1. Structured generation instead of free-form chat

The output is parsed, validated, and normalized through schemas. This makes the result easier to evaluate, render, export, review, and test.

### 2. Deterministic fallback

The system remains usable in a demo even without OpenAI credentials or network availability. This is important for partner walkthroughs where external dependencies should not decide whether the product can be shown.

### 3. Explicit safety boundaries

The instruction draft separates confirmed/request-derived content, local verification needs, and expert-review questions. The system avoids inventing exact settings, tolerances, standards, approvals, or roles.

### 4. Workflow and traceability

The product is not only a generator. It includes version history, reviewer decisions, audit trail, and trial execution evidence, which makes it closer to an enterprise workflow than a one-off prompt demo.

### 5. Production-readiness discipline

The repository includes tests and documentation around authorization, tenancy, request logging, rate limiting, metrics, readiness, Docker packaging, and backup/migration tooling. Remaining blockers are documented instead of hidden.

## Demo story

A strong seven-minute walkthrough can show:

1. Fill a stable manufacturing scenario.
2. Generate a structured instruction.
3. Show source grounding and quality evaluation.
4. Export Markdown/PDF/JSON.
5. Save a version.
6. Record a reviewer decision.
7. Run an operator checklist and save execution evidence.
8. Process a short approved video and show keyframes/stages.
9. Explain the human-review boundary and pilot scope.

Recommended companion doc: [Partner demo flow](partner_demo.md).

## Evidence

Repository artifacts:

Local/generated artifacts:

- `reports/full_audit_2026-06-23.md` — full implementation audit with findings, one safe UI accessibility fix, and verification evidence.
- `reports/partner_demo_pack/` — reproducible synthetic partner-demo evidence pack.
- `reports/demo_eval_report.md` — deterministic 15-scenario demo evaluation report.

The `reports/` folder is intentionally treated as local/private working evidence
for the first public baseline. Curated non-confidential screenshots are copied
to `docs/assets/screenshots/` for publication.

Repository documentation:

- `docs/production_readiness.md` — release classification and production blockers.
- `docs/authorization.md` — organization/project/role permission model.
- `docs/observability.md` — request IDs, logs, metrics, and readiness notes.

Visual artifacts:

- `docs/assets/screenshots/procedra-desktop.png`
- `docs/assets/screenshots/procedra-instruction-result.png`
- `docs/assets/screenshots/procedra-quality-evaluation.png`
- `docs/assets/screenshots/procedra-sources.png`
- `docs/assets/screenshots/procedra-execution-checklist.png`
- `docs/assets/screenshots/procedra-video-keyframes.png`

## What this says about the builder

This project is designed to show more than “I can call an AI API”.

It demonstrates:

- product judgment: choosing a high-value industrial workflow with clear human accountability;
- AI engineering: validation, fallback, retrieval, quality evaluation, video context, and safe uncertainty handling;
- backend depth: FastAPI, Pydantic, SQLite, Docker, tests, migrations, auth, rate limits, metrics, and audit;
- enterprise mindset: roles, approval boundaries, traceability, readiness docs, and demo evidence;
- execution discipline: iterative audits, written handoff, reproducible gates, and clear unresolved-risk tracking.

## Not claimed

The repository does not claim:

- production deployment at an enterprise customer;
- paid traction, revenue, signed contracts, or investment;
- certified legal/regulatory compliance;
- replacement of approved industrial instructions;
- safe operation without domain-expert review;
- unrestricted use with confidential, personal, or regulated data.

## Recommended next proof points

- Run one controlled partner rehearsal with approved non-confidential materials.
- Measure time-to-first-draft against the current manual process.
- Collect expert feedback on correctness, missing fields, terminology, and review usability.
- Convert findings into a narrow pilot scope.
- Decide public/private GitHub visibility and license strategy.
