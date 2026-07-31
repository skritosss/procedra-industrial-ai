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
- Source grounding: checks whether the instruction uses available context,
  records typed provenance, keeps unvalidated claims unverified, avoids
  unsupported exact parameters, and lists local checks.
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
- typed `safety_findings` with code, high/critical severity, explanation, and a
  bounded evidence excerpt.

Generated instructions also expose audit-oriented blocks:

- `observed_facts`: input claims shown without treating source wording as validation;
- `evidence_claims`: the claim text, provenance (`user_claim`,
  `retrieved_unverified`, `validated_local`, or `model_inference`), validation
  status, stable `claim_id`, linked `source_id`, source type, local-verification
  requirement, and optional authenticated validation record;
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

## Fail-closed context pass

After generation, the pipeline discards model-supplied provenance and rebuilds
it from the application request boundary. Generated workflow status is forced to
`ai_draft`; input or retrieved text cannot act as an approval record. The same
deterministic pass checks untrusted context for:

- hazardous actions such as bypassing guards/interlocks or disabling alarms;
- contradictory equipment states;
- exact numeric operating claims that lack application-level validation;
- attempts to hide uncertainty or bypass expert review.

Detected findings add workflow approval blockers and local-verification items.
Critical findings force `risk_level=critical`; unsupported numeric claims force
at least `high`. The structural score remains separate, while the verdict states
that application is blocked.

## Authenticated local validation

Generation never produces `validated_local`. A specific claim in a saved
instruction version can be promoted only through:

```text
POST /api/instructions/history/{instruction_id}/versions/{version}/claims/{claim_id}/validate
```

The endpoint requires an authenticated technologist, safety, quality, or admin
session and records the reviewer identity, role, evidence reference, evidence
SHA-256, comment, and timestamp. The decision is stored with the exact saved
claim and appended as `claim_validated` to the hash-chained audit trail. Text in
the request, retrieved source, LLM response, or client-submitted payload cannot
promote itself. Validation is claim-specific and does not approve the overall
instruction or clear unrelated safety findings.

## Adversarial corpus

`make safety-eval` evaluates the deterministic detector against the versioned
RU/EN corpus at `examples/safety_adversarial_corpus.json`. The report separates
false-positive and false-negative labels from structural score. The current S2
corpus contains 21 hostile and benign cases covering hazards, contradictions,
unit-bearing numeric claims, review override, negation, and distinct-component
states. The current local result is 21/21, precision 1.0000, recall 1.0000, with
zero known false-positive/false-negative labels inside this authored corpus.

## Request Focus Pass

After quality improvement, the pipeline runs a deterministic request-focus pass. It makes the instruction explicitly solve the user's narrow task, adds a scope boundary, and marks that adjacent operations must not be added unless they are required for safety or local applicability checks. The evaluator then scores this through the `request_focus` criterion.

## Current Limitations

This remains a rule-based containment layer. The reproduced hostile cases,
poisoned retrieved source, and mocked-LLM path are covered by regression tests,
and the authored adversarial corpus is reproducible, but the rules can still
have false positives and false negatives outside those cases. The corpus is not
an independent expert-labelled benchmark. These controls do not
replace expert review, an expert-labelled benchmark, process hazard analysis, or
validation by a technologist, safety engineer, and shop-floor supervisor.

The next evaluation step is to add expert-labeled examples and compare:

- deterministic fallback instructions;
- LLM-generated instructions;
- RAG-grounded instructions;
- expert-reviewed final instructions.
