from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.storage.database import apply_migrations, connect_database  # noqa: E402
from app.storage.video_jobs import (  # noqa: E402
    claim_next_video_job,
    complete_video_job,
    create_video_job,
    heartbeat_video_job,
)


def run_probe(*, jobs: int, workers: int, deadline_seconds: float = 30.0) -> dict[str, Any]:
    if jobs < 1 or workers < 1:
        raise ValueError("jobs and workers must be positive")
    with tempfile.TemporaryDirectory(prefix="procedra-video-contention-") as directory:
        database_path = Path(directory) / "probe.sqlite3"
        with connect_database(database_path) as connection:
            apply_migrations(connection)
        for index in range(jobs):
            create_video_job(
                "legacy",
                "legacy",
                None,
                "url",
                {"video_url": "https://example.com/video", "visual_quality": "720", "max_keyframes": 4},
                f"contention-probe-{index:06d}",
                database_path=database_path,
            )

        lock = threading.Lock()
        completed = 0
        claim_counts: Counter[str] = Counter()
        claim_latencies_ms: list[float] = []
        errors: list[str] = []
        deadline = time.monotonic() + deadline_seconds
        started = time.monotonic()

        def consume(worker_index: int) -> None:
            nonlocal completed
            worker_id = f"probe-worker-{worker_index}"
            while time.monotonic() < deadline:
                with lock:
                    if completed >= jobs:
                        return
                claim_started = time.perf_counter()
                try:
                    job = claim_next_video_job(
                        worker_id,
                        lease_seconds=30,
                        database_path=database_path,
                    )
                except Exception as exc:
                    with lock:
                        errors.append(type(exc).__name__)
                    time.sleep(0.002)
                    continue
                latency_ms = (time.perf_counter() - claim_started) * 1000
                if job is None:
                    time.sleep(0.002)
                    continue
                with lock:
                    claim_counts[job.job_id] += 1
                    claim_latencies_ms.append(latency_ms)
                try:
                    heartbeat_ok = heartbeat_video_job(
                        job.job_id,
                        worker_id,
                        lease_seconds=30,
                        database_path=database_path,
                    )
                    completed_ok = complete_video_job(
                        job.job_id,
                        worker_id,
                        {"video_id": job.job_id, "probe": True},
                        database_path=database_path,
                    )
                    if not heartbeat_ok or not completed_ok:
                        raise RuntimeError("lease_integrity_failure")
                except Exception as exc:
                    with lock:
                        errors.append(str(exc)[:80] or type(exc).__name__)
                    continue
                with lock:
                    completed += 1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(consume, range(workers)))

        elapsed_seconds = time.monotonic() - started
        with sqlite3.connect(database_path) as connection:
            succeeded = int(
                connection.execute("SELECT COUNT(*) FROM video_jobs WHERE status = 'succeeded'").fetchone()[0]
            )
            active_leases = int(
                connection.execute(
                    "SELECT COUNT(*) FROM video_jobs WHERE lease_owner IS NOT NULL OR lease_expires_at IS NOT NULL"
                ).fetchone()[0]
            )
            attempt_violations = int(
                connection.execute("SELECT COUNT(*) FROM video_jobs WHERE attempts != 1").fetchone()[0]
            )
        duplicate_claims = sum(max(0, count - 1) for count in claim_counts.values())
        payload = {
            "ok": (
                completed == jobs
                and succeeded == jobs
                and len(claim_counts) == jobs
                and duplicate_claims == 0
                and active_leases == 0
                and attempt_violations == 0
                and not errors
            ),
            "jobs": jobs,
            "workers": workers,
            "completed": completed,
            "succeeded": succeeded,
            "unique_claims": len(claim_counts),
            "duplicate_claims": duplicate_claims,
            "active_leases": active_leases,
            "attempt_violations": attempt_violations,
            "errors": errors[:10],
            "error_count": len(errors),
            "claim_latency_ms": {
                "p50": _percentile(claim_latencies_ms, 0.50),
                "p95": _percentile(claim_latencies_ms, 0.95),
                "max": round(max(claim_latencies_ms), 3) if claim_latencies_ms else 0.0,
            },
            "elapsed_seconds": round(elapsed_seconds, 3),
        }
        return payload


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(ordered[index], 3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an isolated SQLite video-job contention probe")
    parser.add_argument("--jobs", type=int, default=200)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--deadline-seconds", type=float, default=30)
    args = parser.parse_args()
    result = run_probe(jobs=args.jobs, workers=args.workers, deadline_seconds=args.deadline_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
