# Project Specification

## Working Title

Procedra

## Problem

Manufacturing instructions are often prepared manually by engineers, technologists, and experienced shop-floor staff. This process is slow, inconsistent, dependent on individual expertise, and difficult to update when equipment, tooling, or procedures change.

## Target Users

- Process engineers and technologists.
- Shift supervisors and mentors.
- New production employees.
- Internal training and documentation teams.

## MVP Goal

Create a web service that generates a structured work instruction from a text description, optional technical context, local documentation snippets, and video-derived context.

## MVP Inputs

- Task description.
- User level: new operator, experienced operator, engineer.
- Instruction type: workplace preparation, equipment startup, shutdown, inspection, training, maintenance, general.
- Department or production area.
- Equipment name.
- Operation name.
- Optional technical context.
- Optional local documentation context.
- Optional uploaded enterprise `.txt`, `.md`, or text-based `.pdf` documents.
- Optional video file or public video URL.
- Optional video keyframe quality for URL processing.

## MVP Output

- Title.
- Purpose.
- Scope.
- Department and equipment.
- Operator level.
- Required PPE.
- Required tools.
- Safety requirements.
- Hazard zones.
- Prerequisites.
- Step-by-step actions.
- Control points.
- Quality checklist.
- Emergency actions.
- Common mistakes.
- Lifecycle workflow: draft status, required review roles, approval blockers, and next implementation actions.
- Saved instruction version history with reviewer decisions, reviewer roles, approval status, execution-run records, and audit traceability.
- Retrieved documentation sources.
- Video keyframes, timestamps, transcript/context when available.
- Quality evaluation and Markdown rendering.

## Quality Criteria

- Completeness.
- Clarity.
- Consistency with input.
- Logical sequence.
- Suitability for training a new user.
- Safety relevance.
- Presence of control points and emergency actions.

## Current Reliability Requirements

- The API must return a valid instruction even when OpenAI is disabled or unavailable.
- Model output must be parsed and validated before being returned to the user.
- Invalid model output must fall back to the deterministic industrial template.
- Blank optional request fields must be normalized to missing values.
- Instruction step numbers must be sequential and start from 1.
- Video uploads and URL downloads must have a bounded size for local demo stability.
- Uploaded enterprise documents must have a bounded size and must be converted into extracted text before retrieval.
- URL video processing must split text extraction from visual stream download.
- Video URL downloads must reject non-HTTP schemes and unfinished partial files.

## Evaluation Requirements

- Every generated instruction must include a quality evaluation.
- The evaluator must work without external AI calls.
- The evaluator must produce an overall score, criterion-level scores, missing elements, recommendations, and a verdict.
- Evaluation criteria must map to the project assessment criteria: clarity, accuracy, and training effectiveness.
- Every valid generated instruction must pass through a deterministic quality-improvement layer before the final evaluation is returned.
- The quality-improvement layer must not invent exact settings, tolerances, roles, or regulatory references; uncertain details must remain in local verification and expert-review blocks.
- The final instruction must stay narrowly focused on the user's requested operation and explicitly mark the boundary of scope.
- The final instruction must remain an AI draft until workflow blockers are resolved and required enterprise roles review it.

## Completed MVP Scope

- Web UI.
- Local technical-document retrieval.
- Uploaded enterprise-document retrieval.
- Instruction version-history storage, role-gated workflow status updates, execution-run records, and execution summary metrics.
- Video keyframe extraction.
- Optional vision-model analysis of selected frames with conservative fallback
  records when the external model is disabled or unavailable.
- URL video metadata/subtitle extraction.
- Draft instruction generation from video-derived context.
- Review workflow block for expert approval before implementation.

## Deferred Scope

- External production validation of vision-model accuracy on representative
  industrial footage.
- Enterprise integrations.
