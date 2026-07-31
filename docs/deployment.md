# Deployment

This project can run either as local Python processes or as a Dockerized FastAPI
app plus video worker. Docker is the recommended portfolio/demo packaging because
it fixes system dependencies for OpenCV, video decoding, and `yt-dlp`.

## Docker

Python direct dependencies are exactly pinned in `requirements.txt`. CI resolves
that set on Python 3.12, runs `pip check`, and fails on known Python package
vulnerabilities via pinned `pip-audit==2.10.1` before building the image. Refresh
pins and review audit output intentionally; do not silently widen version ranges.

Build and run:

```bash
docker compose up --build
```

Or with the project shortcuts:

```bash
make docker-up
```

Build only:

```bash
docker build -t industrial-instruction-ai:local .
```

Run without Compose:

```bash
docker run --rm -p 127.0.0.1:8000:8000 industrial-instruction-ai:local
```

Open:

```text
http://127.0.0.1:8000/
```

If port `8000` is already busy, override only the host port:

```bash
APP_PORT=8010 docker compose up --build
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

By default Docker Compose starts in deterministic demo mode with `OPENAI_ENABLED=false`. To use OpenAI-backed generation, vision, or embeddings, pass environment variables:

```bash
export OPENAI_API_KEY="..."
OPENAI_ENABLED=true docker compose up --build
```

Compose starts both `industrial-instruction-ai` and `video-job-worker`. For a
non-Compose local run, start `make run` and `make video-worker` in separate
terminals; the UI's video flow remains queued until a worker is available.

Compose also forwards the public-source retrieval settings:

- `PUBLIC_SOURCES_ENABLED`, default `true`;
- `PUBLIC_SOURCES_MAX_RESULTS`, default `15`, validated by the app with an upper bound of `15`.
- `DOCUMENT_MAX_BYTES`, default `15728640`, limits uploaded enterprise documents.
- `DATABASE_PATH`, default `/app/generated/app.sqlite3` in Docker Compose, stores the versioned transactional schema for organizations, users, sessions, instruction versions, audit events, and execution runs in the persistent generated-data volume.
- `API_ACCESS_TOKEN`, default empty, enables bearer-token protection for `/api/*` when set.
- `DEPLOYMENT_MODE`, default `demo`; `production` rejects startup unless the required auth controls are hardened.
- `AUTH_PUBLIC_REGISTRATION_ENABLED` and `AUTH_ALLOW_ROLE_SELF_ASSIGNMENT` must both be `false` in production.
- `AUTH_MIN_PASSWORD_LENGTH` must be at least `12` in production, and the bootstrap `API_ACCESS_TOKEN` must contain at least 32 characters.
- `AUTH_SESSION_TTL_SECONDS` sets the absolute SQLite-backed session lifetime.
  `AUTH_SESSION_IDLE_TIMEOUT_SECONDS` expires inactive sessions, while
  `AUTH_SESSION_RETENTION_SECONDS` bounds how long expired/revoked rows remain
  before opportunistic cleanup during authentication activity.
  Browser sessions use HttpOnly/SameSite=Strict cookies with Secure enabled in
  production and require `X-CSRF-Token` on unsafe methods; bearer API sessions
  remain supported. Logout endpoints revoke sessions server-side.
- `AUTH_INVITATION_TTL_SECONDS` sets the one-time admin invitation lifetime (default: three days).
- `AUTH_MAX_ACTIVE_SESSIONS` caps concurrent active sessions per account.
- `AUTH_RATE_LIMIT_REQUESTS` and `AUTH_RATE_LIMIT_WINDOW_SECONDS` apply a dedicated throttle to registration, login, and invitation acceptance.
- `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS`, and `RATE_LIMIT_WINDOW_SECONDS` limit expensive generation, video, PDF, and document-upload operations.
- Rate-limit buckets live in the shared SQLite database and therefore coordinate local workers and survive process restarts. Protected routes fail closed with `503` if the store is unavailable.
- Compose publishes only on `APP_BIND_HOST=127.0.0.1` by default. Set a broader bind address only behind an intentionally configured firewall/reverse proxy.
- `TRUST_PROXY_HEADERS`, default `false`, should be enabled only behind a trusted reverse proxy that controls `X-Forwarded-For`.
- `TRUSTED_PROXY_IPS` is required when proxy headers are enabled in production; forwarded client IPs from other peers are ignored.
- `VIDEO_ALLOWED_HOSTS` restricts every video/redirect/media/manifest/fragment/subtitle host; it may be empty only in demo mode and is mandatory in production.
- `VIDEO_JOB_LEASE_SECONDS`, `VIDEO_JOB_HEARTBEAT_SECONDS`,
  `VIDEO_JOB_POLL_SECONDS`, and `VIDEO_JOB_MAX_ATTEMPTS` control the single-host
  durable worker. Heartbeat must remain less than half the lease interval.
- `VIDEO_JOB_DOWNLOAD_TIMEOUT_SECONDS`, `VIDEO_JOB_EXTRACT_TIMEOUT_SECONDS`,
  and `VIDEO_JOB_ANALYSIS_TIMEOUT_SECONDS` are hard deadlines for isolated
  blocking stages. `VIDEO_JOB_STAGE_POLL_SECONDS` controls how quickly the
  parent notices cancellation, lease loss, or timeout while maintaining the
  heartbeat.

Generated keyframes, saved instruction versions, uploaded videos, and uploaded document text artifacts are stored in Docker volumes:

- `generated-data` mounted at `/app/generated`;
- `upload-data` mounted at `/app/uploads`.

Compose also enables:

- `init: true` for cleaner signal handling;
- an API healthcheck against the minimal `/ready` endpoint;
- restart policy `unless-stopped` for stable local demo runs.
- a dedicated one-job-at-a-time worker sharing the database and artifact volumes
  with the API service. Its inherited HTTP healthcheck is explicitly disabled
  because the worker does not serve HTTP; container state, restart count, and
  persisted lease/heartbeat/job progress are its honest liveness signals.

## Production Smoke Checklist — local configuration gate only

Run these checks before recording a demo or presenting the project:

```bash
python -m compileall -q app tests scripts
python -m ruff check app tests scripts
python -m mypy app scripts
python -m pip check
python -m pytest -q
docker compose config
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Passing this list is evidence for the local code/configuration baseline only. It
does not validate the current Docker image/runtime, production topology, load,
recovery objectives, external integrations, security posture, or industrial
output safety. A separate daemon-backed build/start/health/persistence/restart
probe was completed for the single-host video-job path on 2026-07-16; its scope
and remaining boundaries are recorded in
`reports/procedra_video_job_daemon_runtime_completion_2026-07-16.md`. A follow-up
drill verified hard stage timeout/cancellation, normal subprocess completion,
and a synthetic SQLite contention probe; see
`reports/procedra_video_job_time_budget_contention_completion_2026-07-16.md`.

## Database migrations, backup, and restore

Schema migrations run idempotently at startup and are recorded in `schema_migrations`. Existing lifecycle JSON files are imported once into SQLite and are not deleted.

Verify and create an online, integrity-checked backup while Compose is running:

```bash
docker compose exec industrial-instruction-ai python scripts/manage_database.py verify
docker compose exec industrial-instruction-ai python scripts/manage_database.py backup \
  --output /app/generated/backups/app-$(date -u +%Y%m%dT%H%M%SZ).sqlite3
```

Restore is an explicit maintenance operation. Stop the application first; the command verifies the source and automatically creates a pre-restore safety backup when the target exists:

```bash
docker compose stop industrial-instruction-ai
docker compose run --rm industrial-instruction-ai python scripts/manage_database.py restore \
  --source /app/generated/backups/app-YYYYMMDDTHHMMSSZ.sqlite3
docker compose up -d industrial-instruction-ai
```

After restore, wait for `healthy`, run `verify`, and exercise login plus a history/audit read. Backup files contain account and enterprise data even though session tokens and passwords are stored only as hashes; protect backup access and retention accordingly.

## Document ownership reconciliation

Document reads never create missing ownership. Before exposing legacy document
files, inspect the reconciliation plan inside the running single-host service:

```bash
docker compose exec industrial-instruction-ai python scripts/reconcile_document_ownership.py
```

The default is a dry run. Scope metadata mismatches, owners from another
organization, ownership conflicts, unreadable documents, and files outside
known project paths block the whole apply. Correct those issues, rerun the plan,
then apply explicitly:

```bash
docker compose exec industrial-instruction-ai python scripts/reconcile_document_ownership.py --apply
```

The apply step registers all candidates in one SQLite transaction and is
idempotent. It does not move, rewrite, quarantine, or delete files.

The local code/configuration checks can be run with:

```bash
make compile
make lint
make typecheck
make test
make pip-check
make docker-config
make video-job-contention
make smoke
```

Then verify the main deterministic API path:

```bash
curl -X POST http://127.0.0.1:8000/api/instructions/generate \
  -H "Content-Type: application/json" \
  -d '{"task":"Подготовить рабочее место оператора перед запуском оборудования"}'
```

## CI

GitHub Actions runs:

- Python dependency installation;
- `compileall` over `app`, `tests`, and `scripts`;
- Ruff linting over `app`, `tests`, and `scripts`;
- mypy typecheck over `app`;
- Python dependency vulnerability audit;
- full `pytest`;
- Docker image build;
- container startup/readiness, non-root UID, and restart smoke;
- Docker Compose config validation.

CI starts the built API image, probes readiness, checks non-root identity, and
restarts it. CI still does not prove shared-volume persistence, worker crash
recovery, load behavior, or production orchestration; those require separate
runtime drills.

The CI environment sets `OPENAI_ENABLED=false`, so tests remain deterministic and do not require API credentials.

## Runtime Notes

- The container runs as a non-root user.
- `ffmpeg`, `libgl1`, `libglib2.0-0`, and `libgomp1` are installed for OpenCV and video processing.
- The API Docker healthcheck calls `/ready`; `/health` remains the lightweight
  liveness endpoint. The dedicated worker has no HTTP healthcheck.
- The image defaults to `OPENAI_ENABLED=false` so direct `docker run` remains deterministic without secrets.
- Runtime limits are validated at startup against configured bounds: upload size,
  document size, video network timeout, vision keyframe count, image size, and
  public-source count. These configuration bounds are not a general safety claim.
- `/ready/details` and `/metrics` are private by default. For partner/prod demos, set `API_ACCESS_TOKEN` and pass `Authorization: Bearer <token>` for API calls and observability endpoints. `METRICS_PUBLIC_ENABLED=true` is a demo-only local-dashboard escape hatch; production configuration rejects it. If used in demo mode, keep the service bound to `127.0.0.1`.
- For a production-mode configuration, also set `DEPLOYMENT_MODE=production`, disable public registration and role self-assignment, configure a non-empty `VIDEO_ALLOWED_HOSTS`, and provision privileged accounts only with the bootstrap API token.
- Browser sessions are authoritative in the web UI. The optional API-token field
  is for bootstrap/service-token flows and does not override an active browser
  session.
- Maintain `VIDEO_ALLOWED_HOSTS` as an approved provider-specific list including required media CDN and caption domains; unlisted redirects and stream hosts fail closed.
- `.env.local`, generated files, uploads, caches, and virtual environments are excluded from the image by `.dockerignore`.
