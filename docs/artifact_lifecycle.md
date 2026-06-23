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

The default mode is dry-run. It prints a JSON report and does not delete files.
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
- Use `cleanup-plan` before `cleanup-delete` when preparing demos.
