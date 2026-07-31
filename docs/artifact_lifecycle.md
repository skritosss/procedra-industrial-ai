# Artifact Lifecycle

The app stores runtime artifacts while processing videos, document indexing, saved instruction review versions, and demo runs:

- `generated/` for extracted keyframes, saved instruction versions, and generated runtime files;
- `uploads/` for uploaded/downloaded videos and extracted uploaded-document text artifacts;
- `reports/` for demo evaluation reports.

`generated/` and `uploads/` are excluded from the Docker image and mounted as Docker volumes in Compose. They can grow quickly during video and document testing, so the project includes a cleanup runner.
Saved instruction versions and saved execution runs share the same `generated/instructions/` store, which keeps trial-run evidence tied to a stable instruction id and version.

By default the cleanup runner only targets transient video artifacts:

- `generated/keyframes/`;
- `uploads/videos/`.

Saved instruction versions, execution-run records in `generated/instructions/`, and uploaded enterprise-document text artifacts in `uploads/documents/` are intentionally not part of the default cleanup scope.

## Dry Run

Preview files older than 24 hours:

```bash
make cleanup-plan
```

or directly:

```bash
.venv/bin/python scripts/cleanup_artifacts.py --max-age-hours 24
```

The same dry-run tool is packaged in the Docker image and can inspect the
mounted Compose volumes:

```bash
docker compose exec industrial-instruction-ai \
  python scripts/cleanup_artifacts.py --max-age-hours 24 --reconcile-video-ownership
```

The default mode is dry-run. It prints a JSON report and does not delete files.
It also reports video ownership rows whose uploaded video and keyframe artifacts
are both absent. This database check is read-only in plan mode.
Schema-v10 video jobs participate in the same cleanup boundary. Artifacts
referenced by `queued` or `running` jobs are protected even when their filesystem
mtime is older than the cutoff. Terminal `succeeded`, `failed`, and `cancelled`
job rows older than the cutoff are reported in plan mode and removed only with
`--delete`.
For readability, the CLI prints only a compact preview of matched files by default. Use `--show-files` to print the full list.
Override the Makefile age threshold when needed:

```bash
make cleanup-plan CLEANUP_MAX_AGE_HOURS=72
```

## Delete

Delete matched files older than 24 hours:

```bash
make cleanup-delete
```

or directly:

```bash
.venv/bin/python scripts/cleanup_artifacts.py --max-age-hours 24 --delete
```

## Safety Rules

- Cleanup roots must be inside the project directory.
- The project root itself cannot be cleaned.
- `.gitkeep` and `.gitignore` files are preserved.
- Symlinks are skipped so cleanup never follows runtime artifact links to external files.
- Empty directories under the selected roots are removed only after matched files are deleted.
- `cleanup-delete` removes a video ownership row only after neither an uploaded
  video nor any keyframe file remains for that tenant-scoped video id.
- Active video-job artifacts and rows are preserved. Cancellation and terminal
  worker failures remove their current transient artifacts immediately when safe.
- Use `cleanup-plan` before `cleanup-delete` when preparing demos.

## Public Scope Audit

Before committing or publishing, run:

```bash
make public-scope-audit
```

The audit is non-destructive. It verifies that known private/runtime paths
remain ignored, checks whether `git add --dry-run .` would include a known
private path, and summarizes local ignored artifact counts and sizes under
`generated/`, `uploads/`, `reports/`, `outputs/`, `output/`, and `tmp/`.
Private filenames are hidden by default; use `--sample-limit` only for an
intentional local review.

This is a path-scope guard, not proof that the contents of an allowed file are
safe to publish. `make public-content-audit` additionally scans tracked and
non-ignored untracked text candidates for high-confidence API/private-key
patterns and fails closed on oversized text. It deliberately does not classify
PII, customer data, licensing, or claim quality; those still require manual
review before staging a public update.
