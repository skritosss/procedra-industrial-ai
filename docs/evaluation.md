# Evaluation Methodology

The evaluation module scores generated manufacturing instructions with a deterministic rubric. It is designed to work during local demos even when OpenAI quota is unavailable.

## Criteria

Each criterion is scored from 0 to 100.

- Completeness: checks whether the instruction includes PPE, tools, safety requirements, hazard zones, prerequisites, steps, control points, and emergency actions.
- Clarity: checks step detail, expected results, verification methods, and the amount of vague wording.
- Input alignment: checks whether the generated instruction preserves department, equipment, and technical-context keywords from the original request.
- Request focus: checks whether the instruction stays narrowly aligned with the user's exact task and explicitly marks the scope boundary.
- Safety: checks PPE, hazard zones, safety requirements, safety notes in steps, and emergency actions.
- Logical sequence: checks step numbering, preparation at the beginning, final verification, and process control points.
- Training value: checks whether the instruction is useful for onboarding through operator level, common mistakes, expected results, verification methods, and quality checklist.
- Source grounding: checks whether the instruction uses available context, separates grounded facts from assumptions, avoids unsupported exact parameters, and lists local checks.
- Domain risk control: checks escalation, stop-work rules, industry-specific risk coverage, and absence of unsafe self-directed actions.
- Implementation readiness: checks result recording, acceptance criteria, emergency scenario coverage, expert review, local verification questions, review roles, approval blockers, and next implementation actions.

## Output

The evaluation returns:

- overall score;
- per-criterion scores;
- strengths;
- issues;
- missing elements;
- recommendations;
- verdict;
- risk level;
- expert-review notes.

Generated instructions also expose three audit-oriented blocks:

- `observed_facts`: facts grounded in the request, retrieved sources, transcript, or frame analysis;
- `local_verification_required`: local parameters, permits, roles, and documents that must be checked before use;
- `expert_review_questions`: practical questions for the supervisor, technologist, occupational-safety specialist, or domain owner.
- `workflow`: lifecycle status, required review roles, approval blockers, and next actions before the instruction can become an approved enterprise document.

## Quality Improvement Pass

After the primary generator returns a valid instruction, the pipeline runs a deterministic quality-improvement pass. This pass does not invent exact machine settings, tolerances, or regulatory references. It only strengthens review-safe structure:

- missing step safety notes and verification methods;
- control points, quality checklist, emergency actions, and common mistakes;
- source-grounding notes through observed facts and local verification items;
- expert-review questions for the supervisor, technologist, occupational-safety specialist, or domain owner;
- profile-specific safety reminders from the selected industry profile.

The improved instruction is then evaluated, rendered to Markdown, and returned through the API.

## Request Focus Pass

After quality improvement, the pipeline runs a deterministic request-focus pass. It makes the instruction explicitly solve the user's narrow task, adds a scope boundary, and marks that adjacent operations must not be added unless they are required for safety or local applicability checks. The evaluator then scores this through the `request_focus` criterion.

## Current Limitations

This is a rule-based evaluator. It is reliable for structural checks, but it does not replace an expert review by a technologist, safety engineer, or shop-floor supervisor.

The next evaluation step is to add expert-labeled examples and compare:

- deterministic fallback instructions;
- LLM-generated instructions;
- RAG-grounded instructions;
- expert-reviewed final instructions.
