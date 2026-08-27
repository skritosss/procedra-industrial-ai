# Evaluation Methodology

The evaluation module scores generated manufacturing instructions with a deterministic rubric. It is designed to work during local demos even when OpenAI quota is unavailable.

## What the score is, and what it is not

**It measures the shape of the document.** Whether the required sections exist,
whether they are filled with something substantive rather than "не указано",
whether steps carry expected results and verification methods, whether declared
hazards are addressed somewhere, whether the work runs in a sensible order.

**It does not measure correctness.** Nothing here knows the machine, the shop, or
the approved procedure. A draft can score in the nineties and still be wrong for
the equipment in front of the operator — wrong torque, wrong sequence, a missing
permit. The verdict text says "структура", never "качество", for this reason.

**It is not independent of what it grades.** The deterministic generator and this
rubric were written together and share a template, so a high score on a generated
draft partly reflects that shared origin. `make quality-discrimination` measures
how much the criteria can actually distinguish, and reports how many checks never
change outcome — currently one of seventy-two.

**One criterion is independent of us.** `regulatory_structure` checks the content
that Order 772n of the Ministry of Labour of Russia (29.10.2021, "Об утверждении
основных требований к порядку разработки и содержанию правил и инструкций по
охране труда, разрабатываемых работодателем") requires an instruction to have.
Each check names the paragraph it comes from, so a safety engineer can verify the
mapping against the order rather than trust our wording. This is the only part of
the score that does not depend on our own opinion of what a good instruction is.

Its limit is stated plainly: the check looks for the observable trace of a
requirement — the words in which first aid, hygiene or the end-of-work procedure
would be described. It can establish that a subject is addressed somewhere in the
document. It cannot establish that it is addressed correctly, and it is not a
compliance certificate.

Two further sources inform the structure rather than the scoring. ГОСТ 3.1105-2011
(ЕСТД) requires a technological instruction to open with its scope and purpose and
to be written in the order the work is performed; both are scored, as
`input_alignment` and `logical_sequence`. The same standard requires document
identification — designation, developer, reviewer, approver, date. Procedra carries
those in the workflow and version history rather than in the instruction body, so
they are not part of this score.

## How a criterion is scored

Each criterion is scored from 0 to 100 as the mean of its checks. A check is
either a boolean or a share between 0 and 1. Shares exist because several
properties are continuous: "steps relate to the task" is not a yes/no fact but a
proportion. While those checks were boolean, a document that already missed the
threshold could not be damaged further, so an instruction with one off-topic step
and an instruction about an entirely different job scored the same.

Checks judge content, not presence. A list whose entries read "не указано" or
"—" is filled in but empty of information, so list checks measure the share of
substantive entries rather than the length of the list.

## Overall score

The overall score is a weighted mean of the criteria, not a plain average. The
weights are declared in `CRITERION_WEIGHTS` in `app/evaluation/quality.py`:

| Weight | Criteria |
|---|---|
| 3.0 | safety |
| 2.0 | domain risk control, source grounding |
| 1.5 | completeness, request focus |
| 1.0 | clarity, logical sequence, input alignment, implementation readiness |
| 0.5 | training value |

When the weakest safety-critical criterion (`safety` or `domain_risk_control`)
falls below `SAFETY_FLOOR`, it becomes the ceiling for the whole document: an
instruction is not rated better than its own safety. Above that floor the
weighted mean governs, so damage to any other criterion still moves the number.
When the ceiling applies, the recommendations state which criterion caused it.

## Criteria

- Completeness: checks whether PPE, tools, safety requirements, hazard zones, prerequisites, steps, control points, and emergency actions are present *and* substantive; control points must also not repeat one another.
- Clarity: checks step detail, substantive expected results, the share of steps carrying a verification method, the amount of vague wording, and whether steps repeat one another.
- Input alignment: checks whether the generated instruction preserves department, equipment, and technical-context keywords from the original request.
- Request focus: checks whether the instruction stays narrowly aligned with the user's exact task and explicitly marks the scope boundary.
- Safety: checks PPE, hazard zones, safety requirements, the share of steps carrying a safety note, emergency actions, and whether each declared hazard zone is actually addressed somewhere in the document rather than only listed.
- Logical sequence: checks step numbering, preparation at the beginning, completion at the end, and that preparation actions precede completion actions. The preparation and completion vocabularies are kept disjoint: while "проверить" counted as both, a fully reversed instruction satisfied both checks.
- Training value: checks whether the instruction is useful for onboarding through operator level, common mistakes, expected results, verification methods, and quality checklist.
- Source grounding: checks whether the instruction uses available context,
  records typed provenance, keeps unvalidated claims unverified, and lists local
  checks. Exact parameters are judged per step: a step stating a torque,
  temperature or tolerance must carry its own verification marker or name the
  parameter in the local-verification list. The earlier form scanned the whole
  document, so a single occurrence of "подтвердить" marked every value in the
  text as handled.
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

**That result must not be read as detection accuracy.** The corpus and the
detector patterns were written by the same author, and the benign cases mirror
the hostile ones. A perfect score therefore demonstrates that the detector still
does what it was written to do — a regression guarantee — and says nothing about
wording the author did not anticipate. Establishing detection accuracy requires a
held-out corpus written after the patterns were frozen, preferably by someone
else, with synonyms, misspellings and word order the patterns do not cover. Until
that exists, the honest expectation is that recall on unseen phrasing is lower
than 1.0.

## Discrimination harness

A criterion that never fails carries no information, however sensible its
wording. `make quality-discrimination` measures this directly: it generates
baseline instructions from the demo scenarios, damages each one in a controlled
way, and reports how the criteria respond. The command runs inside `make smoke`,
so weakening a check breaks the build.

Mutations stay inside the schema on purpose. A model does not return an
instruction with an empty PPE list — that is rejected before evaluation. It
returns one whose PPE list says "не указано", whose steps all expect
"Выполнено", or whose text is padded with the words the checks look for. The
current set covers fourteen such cases, including placeholder lists, vacuous
expected results, repeated steps, reversed work order, keyword stuffing,
off-topic steps, precise values stated without any verification marker, an
internal contradiction about a guard, and claims relabelled as confirmed.

Measured on the 15 demo scenarios: every mutation lowers at least one criterion
it targets. This is a floor, not a quality statement — 51 of 77 checks still pass
on every document in this corpus, which means most checks are not yet tested by
anything the corpus contains. The harness reports that number on each run rather
than hiding it.

The honest limits of this instrument:

- the mutations are authored alongside the checks they exercise, so passing them
  is a regression guarantee, not evidence of external validity;
- baseline instructions come from the deterministic path, so nothing here
  measures the behaviour of a hosted model;
- a document can still be damaged in ways no mutation represents.

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
