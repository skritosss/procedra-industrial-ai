# Production Readiness

Last audited: 2026-07-16

Current evidence source: `reports/procedra_full_audit_2026-07-14.md`, followed by
the bounded G1/O1/U1/U2/V1, visual-QA, D1, S1, and S2 corrections verified on
2026-07-16, plus the W1/W2 durable-video runtime stages. The current local gate
passes 385 pytest tests, Ruff, mypy, compileall, static
asset smoke, path-scope audit, pip integrity, Compose configuration validation,
and API smoke.

This is local prototype evidence, not production validation. Docker Compose
configuration is valid. Follow-up isolated daemon drills built the current
image and verified non-root API/worker startup, API readiness, schema migration,
named-volume persistence, worker lease recovery, hard stage timeout/cancellation,
and a normal video-job subprocess result on one host. This does not validate a
production orchestrator, multi-host/HA behavior, or a capacity ceiling.
No external OpenAI run, live retrieval validation, real industrial video,
customer data, controlled pilot, load test, external penetration test, or
production deployment was performed.

The re-audit's P1 video URL SSRF boundary is now closed for the supported
single-host fetch path: production requires a non-empty host allowlist, all
metadata/media/redirect/manifest/fragment/subtitle URLs share one policy, DNS
answers must be fully public, and sockets are pinned to the validated IP. The
completion evidence is in `reports/video_url_egress_hardening_2026-06-21.md`.

## Current release classification

| Intended use | Decision | Evidence boundary |
|---|---|---|
| Local deterministic demo with synthetic data | **CONDITIONAL GO** | Typed provenance and fail-closed hostile-context checks pass locally; output remains an AI draft. |
| Public GitHub prototype/research artifact | **CONDITIONAL GO** | Requires a separate secret/PII/content/license/claim review; the path-scope gate alone is insufficient. |
| Partner walkthrough | **CONDITIONAL GO** | Synthetic, non-operational scenario only; score and risk labels are not safety evidence. |
| Pilot using real operational data | **NO-GO** | The S1 regression slice is not customer/pilot validation; production controls and evidence are still missing. |
| Internet-facing production / multi-tenant SaaS | **NO-GO** | Unresolved operational gaps, rule-based safety limits, and no production topology/capacity validation. |

Verified baseline:

- Liveness, minimal readiness, authenticated readiness details, private-by-default
  metrics, UI loading, registration/login, authenticated generation, version
  save, workflow transition, and audit retrieval work at local test/smoke level.
- The full local test, lint, typecheck, compile, dependency, static-asset,
  path-scope, API-smoke, and Compose-configuration gates pass.
- Authorization and organization/project isolation have strong automated-test
  coverage; this has not been independently penetration-tested.
- Video artifact ownership is registered only after fallible processing succeeds,
  with rollback coverage for upload/URL extraction and analysis failures.
- Saved evidence claims have stable IDs and source linkage. Only authenticated
  technologist/safety/quality/admin sessions can promote a specific versioned
  claim to `validated_local`; forged client records are stripped and successful
  decisions enter the hash-chained instruction audit trail.

### Critical safety/evaluator finding — locally remediated in S1

The 2026-07-14 audit reproduced five hostile technical-context cases in which
untrusted, contradictory, fabricated, or dangerous details could appear under a
“confirmed context” label while the structural evaluator returned 98–100 and
`risk_level=low`. The workflow still kept the result in `ai_draft`, required
expert review, and did not auto-approve it, but those controls do not remove the
false-confidence risk.

S1 adds typed claim provenance, removes “confirmed” labels from unvalidated
input, forces generated workflow state back to `ai_draft`, and emits explicit
`safety_findings` plus workflow blockers for hazardous actions, contradictions,
unsupported numeric claims, and review-override instructions. The five hostile
cases now return high/critical risk, grounding below 100, and a blocked verdict;
poisoned-source and mocked-LLM regressions cover both generation paths.

This closes the reproduced defect at local deterministic-test level, not the
general problem of industrial semantic validation. The detector remains
rule-based. The S2 authored RU/EN corpus currently passes 21/21 with zero known
false-positive/false-negative labels, but it is not an independent
expert-labelled benchmark and does not cover real customer processes. Evaluator score therefore
still means structural rubric coverage only and must not be presented as
correctness, source truth, safety readiness, regulatory compliance, or pilot
approval.

## Release blockers

### Identity and privileged-role provisioning

Demo mode lets a user choose an operational role for controlled walkthroughs. Production mode fails fast unless public registration and role self-assignment are disabled and a bootstrap API token is configured. The token can create only the first admin and organization. Later users are provisioned through expiring one-time admin invitations bound to the organization, role, and selected projects. Admin-only role, activation, project, and membership operations are transactional and recorded in an immutable audit trail.

Required before external deployment:

- document and test an operational recovery procedure for loss of every admin credential;
- define outbound invitation delivery rather than returning the one-time token to an API client.

Production lifecycle mutations now require an authenticated user session; the static bootstrap token cannot supply reviewer identity.

### Session lifecycle and browser authentication

Sessions are hashed in SQLite and have configurable absolute expiry,
active-session logout, revoke-all, and backward-compatible schema migration.
Registration/login also have dedicated rate limits. The web UI now uses
host-only HttpOnly, SameSite=Strict session cookies (Secure in production) with
a server-bound synchronizer token and double-submit CSRF check. Session and
static API tokens are no longer persisted in `localStorage`. Bearer transport
remains available for non-browser API clients. CSS and JavaScript are now
same-origin static assets, and CSP rejects inline scripts, inline styles,
script/style attributes, objects, frames, and foreign connections.

The detailed auth-stage release audit and finding disposition are recorded in `reports/auth_production_audit_2026-06-18.md`.

Required before external deployment:

- define token rotation/re-authentication policy for long-lived integrations;

### Authorization and data boundaries

Organization and project ownership now scope users, saved histories, audits, execution records, uploaded documents/RAG, videos, and keyframes. Every stored resource is registered against an organization, project, and optional creator. `X-Project-ID` is accepted only for project members; inaccessible projects/resources return `404`. Cross-organization and cross-project tests cover documents, instructions, videos/keyframes, membership, and role escalation. The permission contract is documented in `docs/authorization.md`.

Schema version 10 retains the composite tenant foreign keys introduced in version
7, the admin audit hash chain introduced in version 8, session idle tracking from
version 9, and adds tenant/project-scoped durable video jobs. The tenant
migration rebuilds `project_members` and `resource_ownership` under one
transaction, validates existing rows before the rebuild, and rolls back the
complete schema change on failure. Database verification checks both the
installed foreign-key definitions and both instruction/admin audit chains.

Document listing is now read-only and fail closed: files without matching
ownership are omitted, and GET creates neither directories nor ownership rows.
Retrieval and contextual generation now use the same ownership allowlist and
ignore symlinks, so an unregistered filesystem artifact cannot influence RAG.
The explicit document reconciliation command is dry-run by default, validates
tenant metadata, owner tenancy, known project paths, and existing ownership,
then atomically registers a clean plan only with `--apply`.

Required before external deployment:

- migrate legacy users/data to explicitly assigned organizations;
- define organization deletion/retention and any future cross-organization account transfer policy;
- normalize execution project columns in a separate controlled migration;
- backfill legacy video/keyframe ownership and define partial-video cleanup behavior;
- add DB-to-filesystem ownership reconciliation for videos and keyframes;
- keep `/metrics` and `/ready/details` private in production; production
  configuration rejects `METRICS_PUBLIC_ENABLED=true`, while demo mode may use
  it only for a loopback-bound local dashboard.

### Transactional persistence, migrations, and recovery

Organizations, users, sessions, instruction versions, audit events, and execution runs now use one versioned SQLite schema. Lifecycle mutations are transactional across independent processes on the same host/volume. Audit events are separate append-only rows protected by immutable triggers and a verified SHA-256 chain. Existing JSON records are imported idempotently without deletion. Integrity-checked online backup, guarded restore with a pre-restore safety copy, CLI tooling, and operational documentation are present. Details are recorded in `reports/transactional_storage_completion_2026-06-18.md`.

The current design remains a single-host SQLite deployment contract. It is not an active-active multi-host database, backups are not yet scheduled/encrypted/off-volume, restore drills have no formal RPO/RTO, and tenant retention/deletion across database and file artifacts is not defined.

Required before external deployment:

- define and automate encrypted off-volume backup retention;
- run and document recurring restore drills with RPO/RTO targets;
- define retention, deletion/legal-hold, and cross-store consistency procedures;
- move to PostgreSQL before active-active/multi-host write deployment;
- decide whether external/WORM audit anchoring is required;
- keep uploaded/source data references consistent with instruction versions.

## High-priority hardening

- The shared SQLite rate limiter now coordinates local workers and survives process restarts. Before multi-host deployment, move its state to a dedicated distributed backend and load-test SQLite write contention against lifecycle traffic.
- Structured JSON request/security logs now emit request id, resolved actor and
  tenant/project ids, route template, duration, status, result, and a safe error
  category under a strict no-header/body/query/PII/secret policy. Request metrics
  now use a separate restart-safe, multi-worker SQLite store with bounded route
  cardinality, seven-day retention, and explicit availability/latency SLO alert
  thresholds. Externalize log/metric collection, alert delivery, dashboards,
  retention policy ownership, and monitoring access control before production.
- Readiness checks SQLite and writable runtime paths without applying migrations
  or creating stores during GET. Authenticated details explicitly distinguish
  fallback-only, misconfigured-fallback, and configured-but-not-probed model and
  vision states. A real upstream probe/SLO is still required before claiming
  external dependency health.
- Direct Python dependencies are pinned and CI runs a Python vulnerability gate.
  Container/OS scanning, hash-locked transitive resolution, and an SBOM remain
  required before an external production release.
- Define secret injection and rotation outside ordinary Compose environment variables for production.
- Add request/body limits at the reverse proxy. The queued video path now has
  hard download/extract/analyze deadlines and cancellation; synchronous
  compatibility routes and broader request/model-edge policies remain outside
  that contract.

### Durable video jobs — single-host Compose runtime verified

The primary UI video path now returns `202`, persists job state in SQLite, and
uses a separate lease/heartbeat worker with bounded retry, idempotency,
tenant/project isolation, result retrieval, hard stage timeout/cancellation,
and active-artifact cleanup protection. Automated tests cover concurrent duplicate
enqueue, worker success, retry state, cancellation before and during processing,
cross-tenant access, and expired-lease recovery.

The daemon-backed drill on 2026-07-16 built the image and ran an isolated
Compose project with project-scoped volumes. API and worker both ran as UID
1000, API health/readiness passed, and a worker was killed with exit 137 while a
90-second upload job was at `extracting_keyframes`. The replacement worker did
not claim the live lease early, reclaimed it after expiry as attempt 2, and
completed exactly one job/result/ownership. API restart and force-recreate kept
status, result, keyframes, and both named volumes intact. Runtime testing also
found and fixed an oversized frame-analysis context that made `/result` return
500, and packaged the cleanup runner in the image.

The W2 follow-up isolates download, OpenCV extraction, and analysis in child
process groups while the parent maintains the lease. A deadline, cancellation,
or lease loss terminates the blocking stage. In an isolated Compose drill, a
one-second extraction budget produced `processing_timeout` about 1.1 seconds
after stage start; a separate live extraction was cancelled in 0.18 seconds.
Both left no staged artifact or child process, and the worker remained running.
The same 90-second/50 MiB synthetic input then succeeded normally in about 5.8
seconds with 8 keyframes, 8 analyses, and 6 segments.

A storage-level SQLite probe atomically processed 200 synthetic jobs with 12
concurrent claimers: 200 unique successes, zero duplicate claims, stale leases,
attempt violations, or errors; claim latency was 0.755 ms p50, 11.717 ms p95,
117.113 ms maximum, with 0.402 seconds total elapsed time on this machine. This
is a bounded synthetic contention result, not full media throughput, a production
load limit, or multi-host evidence. The drill also exposed and fixed an inherited
HTTP healthcheck on the worker container: it is now disabled because the worker
serves no HTTP endpoint.

This closes the current single-host blocking-stage and storage-contention slice,
not the broader multi-host/HA blocker. A manual `docker compose start
video-job-worker` was used after the W1 deliberate `docker kill`; a production
orchestrator and its restart semantics remain unverified. The hard process
boundary applies to the primary queued path, not the older synchronous
compatibility endpoints. See
`reports/procedra_video_job_daemon_runtime_completion_2026-07-16.md` and
`reports/procedra_video_job_time_budget_contention_completion_2026-07-16.md`.

## Recommended implementation order

1. Independently label and expand the adversarial corpus with domain experts;
   measure precision/recall across broader multilingual and domain variants.
2. Add container/OS scanning, hash-lock transitive Python resolution, and
   generate an SBOM for every release artifact.
3. Automate encrypted off-volume backup and recurring restore drills with RPO/RTO.
4. Add edge limits, external observability integrations, retention ownership,
   and a documented production architecture decision beyond single-host SQLite.
