# ADR-0001. Abstract the model layer behind provider interfaces

- **Status:** accepted
- **Date:** 2026-07-29
- **Accepted:** 2026-08-03, with stage 1.1 implemented
- **Supersedes:** none

## Context

Procedra calls a hosted model in three places, and each call site constructs an
OpenAI client directly:

| Module | Call | Capability |
|---|---|---|
| `app/generation/pipeline.py:196` | `OpenAI(api_key=…, timeout=…)` → chat completion | Instruction generation |
| `app/vision/frame_analysis.py:51` | `OpenAI(api_key=…, timeout=…)` → responses API | Keyframe analysis |
| `app/retrieval/local_index.py:334` | `OpenAI(api_key=…, timeout=…)` → embeddings | Semantic retrieval |

The vendor name also leaks into the domain model and into persisted data:

- `app/schemas/instruction.py:394` — `generation_mode: Literal["openai", "fallback"]`
- `app/schemas/history.py:15` — `GenerationMode = Literal["openai", "fallback"]`
- `app/vision/frame_analysis.py:155` — `analysis_mode="openai"`
- `app/retrieval/local_index.py:317` — embedding bundle tagged `"openai"`

Because instruction history is stored, `"openai"` is present in existing rows
of the business database. Any rename is a data migration, not just a code change.

Configuration is vendor-shaped as well: `openai_enabled`, `openai_api_key`,
`openai_model`, `openai_vision_model`, `openai_embedding_model`,
`openai_timeout_seconds` in `app/core/settings.py:17-22`.

### Why this now blocks the product

Procedra targets industrial customers who deploy on their own premises. Two
consequences follow directly.

1. **A closed plant network has no route to a hosted API.** Today the only
   offline path is the deterministic fallback, so the product installed inside a
   customer's perimeter silently degrades to a non-AI mode. That is not the
   product being sold.
2. **The first security review question is where data is processed.** With the
   current design the honest answer is "at a third-party hosted API abroad",
   which ends the conversation for most industrial buyers regardless of the
   quality of the rest of the system.

The existing design is not wrong — it was the right shape for a demo. It is
simply the wrong shape for on-premise delivery.

## Decision

Introduce three narrow capability interfaces in a new package `app/providers/`,
and make every existing call site depend on the interface instead of on a vendor
SDK.

```
app/providers/
    base.py         # Protocols: TextProvider, VisionProvider, EmbeddingProvider
    registry.py     # Selection by settings, single construction point
    openai_api.py   # OpenAI and any OpenAI-compatible endpoint (base_url)
    errors.py       # ProviderError hierarchy; SDK exceptions never escape
```

**There is no `deterministic.py`.** The ADR originally listed one; building
stage 1.2 showed it would be a fiction, and the reasoning is recorded in
`app/providers/registry.py`. The text fallback constructs a `WorkInstruction`
from the request object rather than JSON from a prompt, so wrapping it in
`TextProvider` would mean serialising a validated model purely so the caller
could parse it back. Local embeddings for indexed chunks are precomputed at
indexing time and stored on the chunk, so nothing is invoked per query. The
registry returns `None` instead, every caller already has the branch, and a
closed-perimeter deployment gets what it needs: with no model configured,
nothing in this package can reach the network.

Each protocol stays deliberately small — only what the three call sites already
use:

- `TextProvider.complete_json(system, prompt) -> str`
- `VisionProvider.describe_image_json(system, prompt, image_data_url) -> str`
- `EmbeddingProvider.embed(texts) -> tuple[tuple[float, ...], ...]`

Two signatures changed once the call sites were read in detail during stage 1.1.
Both changes make the boundary smaller, and both are recorded here rather than
quietly applied.

**Vision returns raw JSON text, not `FrameAnalysis`.** A domain model in the
return type would drag `app.schemas` inside the provider boundary and require
every future provider — including a local model behind a corporate gateway — to
know the instruction schema. Parsing and validation already sit at the call site,
beside the fallback that handles a bad payload, and they stay there.

**Timeout is provider configuration, not a per-call argument.** All three call
sites set it once when constructing the client and never vary it per request, so
a per-call parameter would be an interface with no user.

Each protocol also exposes `name`, and `EmbeddingProvider` exposes `dimensions`.
The first is what the audit trail records beside a draft — the ADR already
promised "which model produced this" and it needs somewhere to come from. The
second lets a cached embedding bundle be rejected when it was built by a
different model, which the retrieval layer needs the moment a second provider
exists.

### Why an OpenAI-compatible provider rather than one class per vendor

The `openai` SDK accepts a `base_url`. A single `openai_api` provider
parameterised by base URL therefore reaches, without further code:

- OpenAI itself;
- Russian hosted models exposing OpenAI-compatible endpoints;
- self-hosted vLLM, Ollama, llama.cpp and LM Studio inside the customer
  perimeter;
- any corporate LLM gateway the customer already runs.

Vendor-specific providers are added later only where a vendor's native protocol
offers something the compatible endpoint cannot.

### Configuration

Replace the `openai_*` settings with neutral, per-capability ones. Keep the old
names readable for one release so existing `.env` files do not break:

```
LLM_PROVIDER=deterministic          # deterministic | openai_api
LLM_BASE_URL=                       # empty means api.openai.com
LLM_API_KEY=
LLM_TEXT_MODEL=
LLM_VISION_MODEL=
LLM_EMBEDDING_MODEL=
LLM_TIMEOUT_SECONDS=10
LLM_ALLOW_EXTERNAL_CALLS=true       # false hard-blocks any non-loopback egress
```

`LLM_ALLOW_EXTERNAL_CALLS=false` is the closed-perimeter switch. It is enforced
in the provider registry, not left to operator discipline, and it fails loudly
at startup rather than silently at request time.

### Renaming the persisted mode values

`generation_mode` moves from `Literal["openai", "fallback"]` to
`Literal["model", "deterministic"]`, which describes what happened rather than
who was called. The concrete provider and model are recorded in separate,
optional fields so an audit trail can still answer "which model produced this".

Migration is forward-only and additive:

1. Add the new columns and start writing both old and new values.
2. Backfill: `"openai" → "model"`, `"fallback" → "deterministic"`.
3. Widen the schema to accept both, deploy, then narrow to the new values.
4. Drop the old column in a later release.

Reading code accepts both spellings throughout the transition.

## Consequences

### Gained

- The product runs fully inside a closed perimeter with a local model — the
  precondition for on-premise sale.
- Russian hosted models become reachable without touching business logic.
- Vendor SDK exceptions stop leaking into domain code. The current
  `except (OpenAIError, JSONDecodeError, ValidationError, ValueError)` clauses
  collapse into `except ProviderError`.
- Providers become directly testable; tests stop mocking a third-party SDK.
- The audit trail gains the provider and model that produced each instruction —
  useful for the safety story independently of this decision.

### Cost

- Roughly 2-3 weeks of part-time work across four bounded stages.
- A data migration touching stored instruction history. This is the only step
  with a real risk of data loss and must be backed up before it runs.
- Provider output quality varies. The existing evaluation pack (15 scenarios)
  becomes the acceptance gate for adding any new provider, and results must be
  recorded per provider rather than assumed transferable.
- One extra indirection layer for a codebase that currently has none in this
  area.

### Explicitly rejected

- **LangChain or a similar framework.** It would add a large dependency surface
  and its own abstractions to replace roughly 200 lines of adapter code. For an
  on-premise product, a small auditable dependency tree is itself a feature.
- **A vendor class per model provider from the start.** Premature; the
  compatible endpoint covers the near-term targets.
- **Leaving `"openai"` in the persisted schema and mapping at the edges.** It
  keeps a vendor name in the domain model permanently and confuses the audit
  trail once a second provider exists.

## Implementation stages

Each is a separate bounded stage, and behaviour must not change until 1.4.

| Stage | Scope | Done when |
|---|---|---|
| 1.1 | This ADR, protocols in `app/providers/base.py`, no call sites touched | **Done 2026-08-03.** ADR accepted; `app/providers/{__init__,base,errors}.py` added with `tests/test_providers.py`; no call site touched, so the package is inert until 1.2 |
| 1.2 | `openai_api` provider, registry, three call sites migrated | **Done 2026-08-03.** Suite green at 433 tests, no SDK import outside `app/providers/`, enforced by `test_no_vendor_sdk_is_imported_outside_the_provider_package` |
| 1.3 | Settings rename with compatibility, schema and database migration | Existing history readable, both spellings accepted |
| 1.4 | Closed-perimeter profile, egress enforcement, acceptance test with a local model | Application starts and serves with no network route |

## Verification

- No import of `openai` outside `app/providers/` — enforced by a test, not by
  convention.
- Existing tests pass unchanged after stage 1.2.
- A test asserts that `LLM_ALLOW_EXTERNAL_CALLS=false` refuses a non-loopback
  base URL at startup.
- The 15-scenario evaluation pack is run per provider and results recorded
  separately.
- A migration test loads a database containing the old `"openai"` and
  `"fallback"` values and asserts they read correctly after migration.

## Open questions

- Which Russian hosted model to validate against first. Needs a real API key and
  a run of the evaluation pack before any claim about quality is made.
- Which local model is the reference for the closed-perimeter profile, and what
  the minimum hardware requirement is. This determines a line in the commercial
  offer and cannot be guessed.
- Whether vision analysis is viable at all on a local model, or whether the
  closed-perimeter profile ships with video analysis degraded to the
  deterministic path. This must be answered before it is described in any sales
  material.
