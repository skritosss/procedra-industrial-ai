# Observability

The service exposes lightweight runtime signals without external dependencies.

Evidence boundary (2026-07-15): endpoint access rules, local persistence, worker
aggregation, retention behavior, and failure responses are covered by automated
tests. External collectors, alert delivery, dashboards, production retention,
load behavior, and deployed multi-host operation are not validated.

## Headers

Every response includes:

- `X-Request-ID`: caller-provided request id or generated UUID. Oversized or newline-containing values are rejected and replaced;
- `X-Response-Time-ms`: request duration measured by the FastAPI middleware.

## Structured request/security logs

Every completed HTTP request emits one single-line JSON event to stderr. The
schema contains only an explicit allowlist: timestamp, schema version, service,
worker PID, request id, actor/organization/project ids when resolved, HTTP
method, matched route template, duration, status, result category, and safe
error category. Dynamic URL values are never used as the route field.

Headers, cookies, query strings, request/response bodies, email addresses,
names, passwords, invitation/session/API tokens, client IP addresses, and raw
exception text are not logged. Identifier fields are format-checked and known
secret/PII patterns are replaced with `[redacted]`; unknown result/error values
are reduced to a fixed safe category. Each worker configures its own stderr
handler after process creation, so workers do not share mutable logging state.

The JSON stream is intentionally transport-neutral. External log shipping,
retention, and access control remain deployment responsibilities.

## Endpoints

```text
GET /health
```

Basic liveness check.

```text
GET /ready
```

Minimal readiness check. The public response only reports `status` so it can be
used by local healthchecks without exposing the detailed runtime fields returned
by `/ready/details`. It is not a proof that external model/retrieval dependencies
or the broader production topology are healthy.

```text
GET /ready/details
```

Authenticated readiness/configuration check. It reports whether OpenAI mode and
public-source retrieval are enabled, the active public-source limit, whether
runtime artifact directories are writable, and whether both business and metrics
databases pass their health checks. The nested `capabilities` object separates
fallback-only, misconfigured-fallback, and configured-but-not-probed external
model/vision states; it never presents configuration as proof of upstream health.

```text
GET /metrics
```

Durable JSON metrics aggregated across workers and process restarts:

- request, 5xx, slow-request, status, and safe result-category counts;
- average and maximum duration;
- bounded route-template aggregates without actor, tenant, path-value, query,
  body, header, IP, or other PII dimensions;
- availability and latency SLO status plus machine-readable alerts;
- collector/database health and current-worker failed-write count.

The default five-minute SLO window uses minute buckets retained for seven days.
Availability requires at least 99% non-5xx responses. Latency requires at least
95% of responses at or below 2000 ms. Alert evaluation begins after 20 requests:
an availability breach is `critical`, while a latency breach is `warning`.
Before the minimum sample, both SLOs report `insufficient_data` and do not alert.

The metrics SQLite database is deliberately separate from the business/rate
limit database, uses WAL and atomic upserts, and lives on the persistent
`generated` volume. Writes fail open for user traffic; failures increment a
process fallback counter. An unavailable metrics backend makes `/metrics`
return `503` with `metrics_backend_unavailable` and makes `/ready` degraded.

Retention, window, bucket size, latency threshold, SLO percentages, and minimum
sample are configurable through `METRICS_*` settings. `METRICS_DATABASE_PATH`
must differ from `DATABASE_PATH`, retention must cover the query window, and the
window must cover at least one bucket.

`/metrics` is private by default and requires an authenticated user session or
the same `Authorization: Bearer <token>` header as protected API calls. A demo
may deliberately set `METRICS_PUBLIC_ENABLED=true` for a local-only dashboard
while keeping the Compose bind host at `127.0.0.1`. Production configuration
rejects that flag, so production metrics cannot bypass authentication. External
alert delivery and dashboards are deployment integrations and were not added
here.
