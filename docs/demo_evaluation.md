# Demo Evaluation

The demo evaluation pack is a deterministic evidence layer for portfolio, GitHub, and ВКР demonstrations. It proves that the app can generate structured instructions across multiple domains, retrieve public and local sources, evaluate quality, and export PDF files without requiring OpenAI credentials.

## Scenario Pack

`examples/demo_scenarios.json` contains 15 scenarios:

- manufacturing equipment startup and shutdown;
- construction site inspection and hot-work preparation;
- occupational-safety onboarding;
- emergency response;
- public-service document intake;
- housing and utilities incident dispatch;
- healthcare room preparation;
- education laboratory preparation;
- food-production sanitation;
- transport pre-trip inspection;
- information-security phishing response;
- warehouse/forklift area inspection;
- general office equipment preparation.

`examples/video_demo_scenarios.json` contains a manual video-demo manifest with 5 themes. The manifest intentionally stores search hints and expected visual/text signals instead of fixed public URLs, because public video availability and metadata can change. Before a live demo, paste a current URL into the scenario and run the existing video flow from the web UI or API.

Each scenario defines:

- `id` and `title`;
- `expected_profile`;
- a validated `ContextGenerationRequest` payload;
- `max_sources=15` so the retrieval layer is exercised fully.

## Runner

Run the full pack:

```bash
.venv/bin/python scripts/run_demo_eval.py
```

Skip PDF checks for a faster local run:

```bash
.venv/bin/python scripts/run_demo_eval.py --skip-pdf
```

The runner writes:

- `reports/demo_eval_report.json`;
- `reports/demo_eval_report.md`.

By default the runner exits with code `1` when pass rate is below `1.0`, so it can be used as a strict release gate. Override this only for exploratory work:

```bash
.venv/bin/python scripts/run_demo_eval.py --fail-under 0.8
```

## Checks

For every scenario the runner checks:

- instruction title and steps exist;
- at least 5 steps are generated;
- the quality evaluation has all rubric criteria;
- score is at least 60;
- at least 8 sources are returned;
- public sources are the majority;
- source metadata is present;
- expected industry profile appears in retrieved sources;
- safety or verification content is present;
- expert review is required or review questions are generated;
- PDF export returns a valid `%PDF` payload unless skipped.

The report records the active check thresholds so future changes can be compared against the same quality gate.

## Interpreting Results

Use the generated report as a smoke-quality artifact, not as a final legal or safety certification. Good demo readiness means:

- pass rate is 1.0;
- average score is above 70;
- public sources remain the majority;
- risk levels are explainable and conservative;
- failed checks are explicitly reviewed before showing the project.

Before real enterprise use, domain experts must verify current legal editions, local procedures, machine manuals, and site-specific hazards.
