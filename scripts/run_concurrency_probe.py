"""Measure how many concurrent requests the service actually serves.

SQLite allows a single writer. Every authenticated request currently opens a new
connection, re-applies migrations (a `CREATE TABLE IF NOT EXISTS` plus a commit)
and updates `last_seen_at` — two write transactions before any work happens. The
claim that this serialises under load is easy to state and easy to get wrong, so
this probe measures it instead: a real server, real concurrent clients, and the
success rate and latency at each concurrency level.

The number matters beyond engineering. A commercial offer has to name how many
users the product supports, and that figure has to come from a measurement.

Run it against the same build before and after a change and compare:

    python scripts/run_concurrency_probe.py --label before
    python scripts/run_concurrency_probe.py --label after
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_REPORT = PROJECT_ROOT / "reports" / "concurrency_probe.json"
DEFAULT_LEVELS = (1, 2, 4, 8, 16, 32)


@dataclass
class EndpointResult:
    endpoint: str
    concurrency: int
    requests: int
    succeeded: int
    failed: int
    status_counts: dict[str, int] = field(default_factory=dict)
    success_rate: float = 0.0
    requests_per_second: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_max_ms: float = 0.0


@dataclass
class ProbeReport:
    label: str
    levels: list[int]
    requests_per_level: int
    results: list[EndpointResult]
    max_concurrency_fully_served: dict[str, int]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for(url: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError(f"Server did not become ready at {url}")


def _request(url: str, token: str | None) -> tuple[int, float]:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            status = int(response.status)
    except urllib.error.HTTPError as error:
        error.read()
        status = int(error.code)
    except (urllib.error.URLError, OSError, TimeoutError):
        status = 0
    return status, (time.perf_counter() - started) * 1000


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return round(ordered[index], 2)


def _measure(url: str, token: str | None, concurrency: int, total: int) -> EndpointResult:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        outcomes = list(pool.map(lambda _: _request(url, token), range(total)))
    elapsed = time.perf_counter() - started

    statuses = [status for status, _ in outcomes]
    latencies = [latency for _, latency in outcomes]
    succeeded = sum(1 for status in statuses if 200 <= status < 300)
    counts: dict[str, int] = {}
    for status in statuses:
        key = "connection_error" if status == 0 else str(status)
        counts[key] = counts.get(key, 0) + 1
    return EndpointResult(
        endpoint=url.rsplit("/", 1)[-1] or url,
        concurrency=concurrency,
        requests=total,
        succeeded=succeeded,
        failed=total - succeeded,
        status_counts=counts,
        success_rate=round(succeeded / total, 4) if total else 0.0,
        requests_per_second=round(total / elapsed, 1) if elapsed else 0.0,
        latency_p50_ms=_percentile(latencies, 0.50),
        latency_p95_ms=_percentile(latencies, 0.95),
        latency_max_ms=round(max(latencies), 2) if latencies else 0.0,
    )


def _register_session(base_url: str) -> str:
    payload = json.dumps(
        {
            "email": "probe@example.com",
            "full_name": "Concurrency Probe",
            "password": "probe-password-123",
            "role": "operator",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/auth/register",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read())
    token = body.get("access_token") or body.get("token")
    if not token:
        raise RuntimeError(f"Registration did not return a bearer token: {sorted(body)}")
    return str(token)


def run(label: str, levels: tuple[int, ...], per_level: int) -> ProbeReport:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="procedra-concurrency-") as workdir:
        root = Path(workdir)
        environment = {
            **os.environ,
            "DEPLOYMENT_MODE": "demo",
            "ALLOW_UNAUTHENTICATED_ACCESS": "false",
            "DATABASE_PATH": str(root / "app.sqlite3"),
            "METRICS_DATABASE_PATH": str(root / "metrics.sqlite3"),
            "AUTH_PUBLIC_REGISTRATION_ENABLED": "true",
            "OPENAI_ENABLED": "false",
        }
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            _wait_for(f"{base_url}/health")
            token = _register_session(base_url)
            results: list[EndpointResult] = []
            for concurrency in levels:
                results.append(_measure(f"{base_url}/api/auth/me", token, concurrency, per_level))
                results.append(_measure(f"{base_url}/ready", None, concurrency, per_level))
        finally:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()

    fully_served: dict[str, int] = {}
    for result in results:
        if result.success_rate == 1.0:
            previous = fully_served.get(result.endpoint, 0)
            fully_served[result.endpoint] = max(previous, result.concurrency)
        else:
            fully_served.setdefault(result.endpoint, 0)
    return ProbeReport(
        label=label,
        levels=list(levels),
        requests_per_level=per_level,
        results=results,
        max_concurrency_fully_served=fully_served,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="unlabelled", help="Name for this run, e.g. before/after.")
    parser.add_argument("--requests", type=int, default=120, help="Requests per concurrency level.")
    parser.add_argument("--levels", default=",".join(str(level) for level in DEFAULT_LEVELS))
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    levels = tuple(int(item) for item in args.levels.split(",") if item.strip())
    report = run(args.label, levels, args.requests)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    destination = args.output.with_name(f"{args.output.stem}_{report.label}{args.output.suffix}")
    destination.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\n{'endpoint':14} {'conc':>5} {'ok%':>7} {'rps':>8} {'p50 ms':>9} {'p95 ms':>9}  statuses")
    for result in report.results:
        print(
            f"{result.endpoint:14} {result.concurrency:5} {result.success_rate * 100:6.1f}% "
            f"{result.requests_per_second:8.1f} {result.latency_p50_ms:9.2f} {result.latency_p95_ms:9.2f}"
            f"  {result.status_counts}"
        )
    print(f"\nCONCURRENCY_PROBE label={report.label} fully_served={report.max_concurrency_fully_served}")
    print(f"report: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
