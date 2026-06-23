# GitHub publication checklist

This checklist prepares Procedra for a strong but safe GitHub publication.

## Publication goal

Position the repository as a serious AI/product engineering portfolio project:

- clear industrial problem;
- working product prototype;
- real technical depth;
- screenshots and reproducible demo artifacts;
- honest production-readiness boundaries;
- no invented traction, clients, revenue, or deployment claims;
- no secrets or runtime data committed.

## Suggested repository positioning

Recommended title:

```text
Procedra — Industrial Instruction AI
```

Possible repository names:

- `procedra`
- `procedra-industrial-ai`
- `industrial-instruction-ai`

Recommended short description:

```text
AI workflow prototype for generating review-ready industrial work instructions from tasks, documents, sources, and video context.
```

Suggested GitHub topics:

```text
ai, fastapi, industrial-ai, rag, manufacturing, pydantic, docker, computer-vision, workflow, audit-trail
```

## What to include

Recommended for the first public commit:

- `README.md`
- `app/`
- `tests/`
- `docs/`
- `examples/`
- `.github/workflows/`
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `.dockerignore`
- selected non-sensitive screenshots under `docs/assets/screenshots/`

Recommended to keep out of Git:

- `.env.local`
- real API keys or tokens;
- generated SQLite databases;
- uploads;
- local runtime volumes;
- `.venv/`;
- `__pycache__/`;
- `.DS_Store`;
- `PROJECT_HANDOFF.md` unless the repository is private and the internal
  continuation context is intentionally included;
- `outputs/`;
- `output/`;
- `tmp/`;
- `reports/` unless a specific public evidence subset is deliberately selected;
- bulky gate logs and generated report binaries;
- private partner materials;
- confidential customer documents or videos;
- bulky logs unless they are deliberate audit evidence.

## Safety checks before commit

Run:

```bash
git status --short
git check-ignore -v .env.local generated uploads outputs output tmp reports PROJECT_HANDOFF.md app/__pycache__/main.cpython-312.pyc app/.DS_Store
rg -l "OPENAI_API_KEY|API_ACCESS_TOKEN|sk-[A-Za-z0-9_-]+|BEGIN .*PRIVATE KEY|password|secret|token" \
  --glob '!.env.local' \
  --glob '!generated/**' \
  --glob '!uploads/**' \
  --glob '!.venv/**' \
  .
```

Then manually inspect any matches before staging.

## Recommended first commit message

```text
Initial public portfolio baseline for Procedra
```

## License decision

Before public release, choose one:

1. Private GitHub repository shared selectively with recruiters/partners.
2. Public repository with no open-source license yet, meaning source-visible but all rights reserved by default.
3. Public open-source repository with MIT or Apache-2.0 license.

Recommendation for a project intended to impress industrial partners: start private or public-without-open-source-license until commercial/IP plans are clearer. Add an explicit license later when the strategic direction is decided.

## Profile / pinned-repo framing

Suggested pinned-repo sentence:

```text
Built an industrial AI workflow prototype that turns task descriptions, documents, public sources, and video context into review-ready work instructions with validation, quality evaluation, expert review, execution evidence, and audit trail.
```

If writing in Russian:

```text
Разработал AI-прототип для подготовки проверяемых производственных инструкций из описания задачи, документов, открытых источников и видео-контекста с валидацией, оценкой качества, экспертным согласованием, чеклистом исполнения и audit trail.
```

## Final pre-push gate

Recommended:

```bash
make smoke
make demo-eval
make partner-demo-pack
```

For a heavier baseline:

```bash
make compile
make lint
make typecheck
make test
make pip-check
make docker-config
```
