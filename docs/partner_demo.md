# Industrial Partner Demo Flow

This checklist prepares the project for a controlled demonstration to an industrial partner. It is intentionally practical: run the checks, show a small number of strong scenarios, and state the review boundaries clearly.

## Pre-Demo Checks

Run these commands before the meeting:

```bash
make smoke
make safety-eval
make demo-eval
make cleanup-plan
make partner-demo-pack
```

Expected result:

- all tests pass;
- demo evaluation passes 15/15 scenarios;
- `/health` and the minimal `/ready` endpoint are available;
- `/ready/details` and `/metrics` require `API_ACCESS_TOKEN`, unless demo mode
  deliberately enables `METRICS_PUBLIC_ENABLED=true` for a loopback-only local
  dashboard; production configuration rejects public metrics;
- `cleanup-plan` only previews old generated artifacts.
- `partner-demo-pack` produces an isolated, synthetic, reproducible fallback
  under `reports/partner_demo_pack/` without writing to the application database
  or Docker runtime volumes.

These checks prove reproducibility of a local demo flow. They do not prove
industrial correctness, safety readiness, customer validation, pilot readiness,
Docker runtime behavior, or production readiness.

## Reproducible Evidence Pack

`make partner-demo-pack` executes the complete governance story against a
temporary database: technologist registration, grounded generation, version
save, expert review, approval, trial execution evidence, audit trail, PDF
export, local fallback-video keyframes, semantic stages, and video-grounded
generation. It saves JSON, Markdown, PDF, a clearly marked synthetic fallback
video, extracted frames, hashes, a pilot result summary, and a seven-minute talk
track.

The included video is deliberately synthetic and proves flow reproducibility
only. Until the critical provenance/evaluator gap is closed, keep the walkthrough
synthetic; do not substitute real operational footage or use its score/risk label
to make a safety claim. The core demonstration must not depend on a public video
URL or a live OpenAI call.

The generated `pilot-summary.md` is the safest artifact to send after a
walkthrough. It separates what was tested, what was not tested, included
evidence, and the next controlled-pilot step without claiming production
readiness, customer validation, safety certification, or measured business
impact.

If Docker is available:

```bash
make docker-config
make docker-build
```

## Recommended Live Flow

1. Open `http://127.0.0.1:8000/`.
2. Keep the interface in Russian for the industrial user.
3. Use the sample case button to fill a stable manufacturing scenario.
4. Generate an instruction with public/documentation sources enabled and source count set to 15.
5. Show the instruction, structural quality evaluation, source tab, Markdown,
   JSON, and PDF export. State that score and `risk_level` are not correctness or
   safety verdicts.
6. Save the generated instruction as a history version, record a workflow decision with reviewer role, open the operator checklist, and save one execution run with executor, checked steps, quality checks, and notes.
7. Process one short public video or prepared local video, then generate an instruction from the video-derived context.
8. Show the frame timeline, semantic video stages, frame-analysis uncertainty notes, and step-to-frame links.
9. Close with a bounded pilot proposal: one instruction family, one approved
   document set, named reviewers, and baseline/target measurements.

## Strong Demo Scenarios

- Manufacturing: подготовка/запуск оборудования, проверка ограждений, аварийная остановка, журнал смены.
- Construction: проверка строительной площадки, СИЗ, ограждение зоны, запрет работ при опасности.
- Occupational safety: инструктаж, допуск, фиксация отклонений, ответственное лицо.
- Emergency response: пожарная тревога, эвакуация, оповещение, запрет возврата без разрешения.
- Information security: фишинговое письмо, запрет перехода по ссылкам, эскалация в ИБ.

## What To Emphasize

- The result is an AI draft for workflow demonstration, not an approved or
  review-ready-for-use industrial instruction.
- Public sources are prioritized before local demo documents and are visible to the reviewer.
- The UI shows typed provenance, validation status, local verification needs,
  expert-review questions, and explicit safety blockers. An `unverified` claim
  is never proof that the underlying statement is true.
- A saved claim can become `validated_local` only through an authenticated,
  version-scoped reviewer decision with evidence reference/hash and audit event;
  this claim-level decision does not approve the whole instruction.
- Saved versions now support execution-run records, so the demo can show traceability from AI draft to trial execution evidence.
- Workflow decisions are role-aware: final approval is limited to technologist, safety, quality, or admin roles.
- Video is split into text extraction and visual keyframe extraction, which keeps subtitles/description useful even when frames are imperfect.
- PDF export includes the service watermark and source/evaluation sections.

## Honest Boundaries

- The 2026-07-14 critical false-confidence cases are locally covered by S1:
  hostile, contradictory, fabricated-numeric, poisoned-source, and mocked-LLM
  inputs stay unverified and return high/critical blockers. This is regression
  evidence, not customer validation or safety certification.
- Evaluator score and `risk_level` must not be presented as proof of correctness,
  source validation, safety, compliance, pilot acceptance, or production fitness.
- Legal edition, applicability, and enterprise-specific procedures must be verified by a domain expert.
- Exact machine settings, tolerances, permits, and responsible roles can be
  echoed from untrusted context and must be independently verified; do not claim
  that the system reliably refuses to invent or confirm them.
- Vision analysis requires OpenAI configuration for detailed image descriptions; otherwise the fallback marks visual uncertainty.
- Long or inaccessible public videos may fail because of platform restrictions, duration limit, or `yt-dlp` support.
- This is not a replacement for approved local instructions, occupational-safety procedures, or technologist sign-off.

## Partner Questions To Ask

- Which instruction types create the most manual work today?
- Which local documents should become the first approved knowledge base?
- What fields are mandatory in the partner's instruction template?
- Who must approve generated drafts before production use?
- What success metric matters most: time saved, completeness, onboarding speed, or audit traceability?
