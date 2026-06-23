# Production Readiness

Last audited: 2026-06-20

The current comprehensive re-audit is recorded in
`reports/full_production_reaudit_2026-06-20.md`: 27 unresolved findings
(9 P1, 14 P2, 4 P3), no P0, and eight safely corrected defect groups. Its local
and isolated Docker gates pass 296 tests plus Ruff, strict mypy, compileall, pip
integrity, Compose validation, hardened `/ready`, and database verification.

The re-audit's P1 video URL SSRF boundary is now closed for the supported
single-host fetch path: production requires a non-empty host allowlist, all
metadata/media/redirect/manifest/fragment/subtitle URLs share one policy, DNS
answers must be fully public, and sockets are pinned to the validated IP. The
completion evidence is in `reports/video_url_egress_hardening_2026-06-21.md`.

## Current release classification

The current build is suitable for a controlled local or partner demo with trusted participants. It is not approved for an internet-facing production deployment or for storing regulated enterprise instruction data.

Verified baseline:

- Docker Python 3.12 image builds and the Compose service reaches `healthy`.
- Liveness, readiness, metrics, UI loading, registration/login, authenticated generation, version save, workflow transition, and audit retrieval work in the deterministic demo configuration.
- The full test, lint, typecheck, compile, dependency, and Compose configuration gates pass.
- The container runs as a non-root user and persistent generated/upload paths are mounted as named volumes.

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

- add idle timeout, token rotation, and scheduled cleanup of expired rows;

### Authorization and data boundaries

Organization and project ownership now scope users, saved histories, audits, execution records, uploaded documents/RAG, videos, and keyframes. Every stored resource is registered against an organization, project, and optional creator. `X-Project-ID` is accepted only for project members; inaccessible projects/resources return `404`. Cross-organization and cross-project tests cover documents, instructions, videos/keyframes, membership, and role escalation. The permission contract is documented in `docs/authorization.md`.

Schema version 7 rebuilds `project_members` and `resource_ownership` under one
transaction and enforces their organization/project/user relationships with
composite SQLite foreign keys. The migration validates all existing rows before
the rebuild, rolls back the complete schema change on failure, and database
verification checks the installed foreign-key definitions.

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
- decide which metrics and readiness details may be visible outside the trusted network.

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
- Make readiness test real dependencies. It now checks the SQLite connection as well as writable runtime paths; external model and retrieval dependencies still need clearly separated degraded-state semantics.
- Pin deployable dependency versions and add automated vulnerability/container scanning plus an SBOM.
- Define secret injection and rotation outside ordinary Compose environment variables for production.
- Add request/body limits at the reverse proxy and verify timeout/cancellation behavior for long video and model operations.

## Recommended implementation order

1. Production/demo mode contract and privileged-role provisioning.
2. Session expiry, revocation/logout, and auth-endpoint throttling.
3. Permission matrix plus tenant/project ownership enforcement.
4. Transactional lifecycle/audit persistence with migrations and recovery tooling.
5. Shared rate limiting, structured observability, deployment security, and failure-mode tests.
6. Re-run the partner-demo evidence flow, then proceed to deferred UI polish and the portfolio case study.
