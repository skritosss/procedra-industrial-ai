# Industrial Partner Demo Flow

This checklist prepares the project for a controlled demonstration to an industrial partner. It is intentionally practical: run the checks, show a small number of strong scenarios, and state the review boundaries clearly.

## Pre-Demo Checks

Run these commands before the meeting:

```bash
make smoke
make demo-eval
make cleanup-plan
make partner-demo-pack
```

Expected result:

- all tests pass;
- demo evaluation passes 15/15 scenarios;
- `/health`, `/ready`, and `/metrics` are available;
- `cleanup-plan` only previews old generated artifacts.
- `partner-demo-pack` produces an isolated, synthetic, reproducible fallback
  under `reports/partner_demo_pack/` without writing to the application database
  or Docker runtime volumes.

## Reproducible Evidence Pack

`make partner-demo-pack` executes the complete governance story against a
temporary database: technologist registration, grounded generation, version
save, expert review, approval, trial execution evidence, audit trail, PDF
export, local fallback-video keyframes, semantic stages, and video-grounded
generation. It saves JSON, Markdown, PDF, a clearly marked synthetic fallback
video, extracted frames, hashes, and a seven-minute talk track.

The included video is deliberately synthetic and proves flow reliability only.
For the actual meeting, replace it with a short, approved, non-confidential
partner clip. The core demonstration must not depend on a public video URL or a
live OpenAI call.

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
5. Show the instruction, quality evaluation, source tab, Markdown, JSON, and PDF export.
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

- The result is a review-ready AI draft, not an uncontrolled final instruction.
- Public sources are prioritized before local demo documents and are visible to the reviewer.
- The system separates observed facts, local verification requirements, and expert-review questions.
- Saved versions now support execution-run records, so the demo can show traceability from AI draft to trial execution evidence.
- Workflow decisions are role-aware: final approval is limited to technologist, safety, quality, or admin roles.
- Video is split into text extraction and visual keyframe extraction, which keeps subtitles/description useful even when frames are imperfect.
- PDF export includes the service watermark and source/evaluation sections.

## Honest Boundaries

- Legal edition, applicability, and enterprise-specific procedures must be verified by a domain expert.
- Exact machine settings, tolerances, permits, and responsible roles are not invented by the system.
- Vision analysis requires OpenAI configuration for detailed image descriptions; otherwise the fallback marks visual uncertainty.
- Long or inaccessible public videos may fail because of platform restrictions, duration limit, or `yt-dlp` support.
- This is not a replacement for approved local instructions, occupational-safety procedures, or technologist sign-off.

## Partner Questions To Ask

- Which instruction types create the most manual work today?
- Which local documents should become the first approved knowledge base?
- What fields are mandatory in the partner's instruction template?
- Who must approve generated drafts before production use?
- What success metric matters most: time saved, completeness, onboarding speed, or audit traceability?
