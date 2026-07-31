from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import pytest

from app.core.observability import RuntimeMetrics
from app.storage.metrics_store import (
    _record_request_metric,
    initialize_metrics_store,
    metrics_store_is_read_only_ready,
    metrics_snapshot,
)


def test_metrics_readiness_is_read_only_and_requires_initialized_store(tmp_path: Path) -> None:
    database_path = tmp_path / "missing" / "metrics.sqlite3"

    assert metrics_store_is_read_only_ready(database_path) is False
    assert not database_path.exists()
    assert not database_path.parent.exists()

    initialize_metrics_store(database_path)
    before = database_path.stat().st_mtime_ns
    assert metrics_store_is_read_only_ready(database_path) is True
    assert database_path.stat().st_mtime_ns == before


def _record_metrics_in_process(database_path: str, worker: int) -> int:
    for index in range(20):
        _record_request_metric(
            Path(database_path),
            method="GET",
            route_template="/api/items/{item_id}",
            status_code=200,
            result_category="success",
            duration_ms=float(worker + index),
            latency_threshold_ms=2_000.0,
            bucket_seconds=60,
            retention_seconds=3600,
            now=1_000.0,
        )
    return worker


def test_runtime_metrics_records_snapshots_and_resets() -> None:
    metrics = RuntimeMetrics()

    metrics.record(status_code=200, duration_ms=10.0)
    metrics.record(status_code=500, duration_ms=30.0)
    snapshot = metrics.snapshot()

    assert snapshot["request_count"] == 2
    assert snapshot["error_count"] == 1
    assert snapshot["server_error_count"] == 1
    assert snapshot["average_duration_ms"] == 20.0
    assert snapshot["status_counts"] == {"200": 1, "500": 1}

    metrics.reset()
    reset_snapshot = metrics.snapshot()

    assert reset_snapshot["request_count"] == 0
    assert reset_snapshot["error_count"] == 0
    assert reset_snapshot["status_counts"] == {}


def test_durable_metrics_aggregate_and_evaluate_slos(tmp_path: Path) -> None:
    database_path = tmp_path / "metrics.sqlite3"
    samples = [
        (200, "success", 100.0),
        (200, "success", 3_000.0),
        (503, "server_error", 4_000.0),
        (401, "security_denied", 50.0),
    ]
    for status, result, duration in samples:
        _record_request_metric(
            database_path,
            method="GET",
            route_template="/api/resources/{resource_id}",
            status_code=status,
            result_category=result,
            duration_ms=duration,
            latency_threshold_ms=2_000.0,
            bucket_seconds=60,
            retention_seconds=3600,
            now=1_000.0,
        )

    snapshot = metrics_snapshot(
        database_path,
        window_seconds=300,
        bucket_seconds=60,
        retention_seconds=3600,
        availability_slo_percent=99.0,
        latency_slo_percent=95.0,
        latency_threshold_ms=2_000.0,
        alert_min_requests=1,
        now=1_001.0,
    )

    assert snapshot["request_count"] == 4
    assert snapshot["server_error_count"] == 1
    assert snapshot["slow_request_count"] == 2
    assert snapshot["status_counts"] == {"200": 2, "401": 1, "503": 1}
    assert snapshot["result_counts"] == {
        "security_denied": 1,
        "server_error": 1,
        "success": 2,
    }
    assert snapshot["slo"]["availability"]["status"] == "breached"
    assert snapshot["slo"]["latency"]["status"] == "breached"
    assert {alert["code"] for alert in snapshot["alerts"]} == {
        "availability_slo_breach",
        "latency_slo_breach",
    }
    assert snapshot["routes"][0]["route_template"] == "/api/resources/{resource_id}"


def test_durable_metrics_survive_store_reinitialization(tmp_path: Path) -> None:
    database_path = tmp_path / "restart-metrics.sqlite3"
    _record_request_metric(
        database_path,
        method="POST",
        route_template="/api/auth/login",
        status_code=401,
        result_category="security_denied",
        duration_ms=25.0,
        latency_threshold_ms=2_000.0,
        bucket_seconds=60,
        retention_seconds=3600,
        now=1_000.0,
    )

    initialize_metrics_store(database_path)
    snapshot = metrics_snapshot(
        database_path,
        window_seconds=300,
        bucket_seconds=60,
        retention_seconds=3600,
        availability_slo_percent=99.0,
        latency_slo_percent=95.0,
        latency_threshold_ms=2_000.0,
        alert_min_requests=20,
        now=1_001.0,
    )

    assert snapshot["request_count"] == 1
    assert snapshot["status_counts"] == {"401": 1}
    assert snapshot["slo"]["availability"]["status"] == "insufficient_data"
    assert snapshot["alerts"] == []


def test_durable_metrics_are_atomic_across_threads(tmp_path: Path) -> None:
    database_path = tmp_path / "thread-metrics.sqlite3"

    def record(index: int) -> None:
        _record_request_metric(
            database_path,
            method="GET",
            route_template="/health",
            status_code=200,
            result_category="success",
            duration_ms=float(index),
            latency_threshold_ms=2_000.0,
            bucket_seconds=60,
            retention_seconds=3600,
            now=1_000.0,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(record, range(40)))
    snapshot = metrics_snapshot(
        database_path,
        window_seconds=300,
        bucket_seconds=60,
        retention_seconds=3600,
        availability_slo_percent=99.0,
        latency_slo_percent=95.0,
        latency_threshold_ms=2_000.0,
        alert_min_requests=20,
        now=1_001.0,
    )

    assert snapshot["request_count"] == 40


def test_durable_metrics_are_atomic_across_worker_processes(tmp_path: Path) -> None:
    database_path = tmp_path / "process-metrics.sqlite3"
    try:
        with ProcessPoolExecutor(max_workers=4) as executor:
            workers = list(executor.map(_record_metrics_in_process, [str(database_path)] * 4, range(4)))
    except (NotImplementedError, PermissionError) as exc:
        pytest.skip(f"Process pools are unavailable in this sandbox: {exc}")

    assert workers == [0, 1, 2, 3]
    snapshot = metrics_snapshot(
        database_path,
        window_seconds=300,
        bucket_seconds=60,
        retention_seconds=3600,
        availability_slo_percent=99.0,
        latency_slo_percent=95.0,
        latency_threshold_ms=2_000.0,
        alert_min_requests=20,
        now=1_001.0,
    )
    assert snapshot["request_count"] == 80


def test_durable_metrics_retention_removes_expired_buckets(tmp_path: Path) -> None:
    database_path = tmp_path / "retention-metrics.sqlite3"
    for now in (100.0, 1_000.0):
        _record_request_metric(
            database_path,
            method="GET",
            route_template="/health",
            status_code=200,
            result_category="success",
            duration_ms=10.0,
            latency_threshold_ms=2_000.0,
            bucket_seconds=60,
            retention_seconds=300,
            now=now,
        )
    snapshot = metrics_snapshot(
        database_path,
        window_seconds=300,
        bucket_seconds=60,
        retention_seconds=300,
        availability_slo_percent=99.0,
        latency_slo_percent=95.0,
        latency_threshold_ms=2_000.0,
        alert_min_requests=1,
        now=1_001.0,
    )

    assert snapshot["request_count"] == 1
