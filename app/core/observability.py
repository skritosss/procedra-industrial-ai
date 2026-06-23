from dataclasses import dataclass, field
import sqlite3
from threading import Lock
from time import perf_counter
from typing import Any

from app.core.settings import Settings
from app.storage.metrics_store import metrics_snapshot, record_request_metric


@dataclass
class RuntimeMetrics:
    started_at: float = field(default_factory=perf_counter)
    request_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    durable_write_failure_count: int = 0
    status_counts: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def record(self, *, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self.request_count += 1
            self.total_duration_ms += duration_ms
            status_key = str(status_code)
            self.status_counts[status_key] = self.status_counts.get(status_key, 0) + 1
            if status_code >= 500:
                self.error_count += 1

    def snapshot(self) -> dict:
        with self._lock:
            uptime_seconds = perf_counter() - self.started_at
            average_duration_ms = self.total_duration_ms / self.request_count if self.request_count else 0.0
            return {
                "uptime_seconds": round(uptime_seconds, 3),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "server_error_count": self.error_count,
                "average_duration_ms": round(average_duration_ms, 3),
                "status_counts": dict(sorted(self.status_counts.items())),
                "durable_write_failure_count": self.durable_write_failure_count,
            }

    def record_durable_write_failure(self) -> None:
        with self._lock:
            self.durable_write_failure_count += 1

    def reset(self) -> None:
        with self._lock:
            self.started_at = perf_counter()
            self.request_count = 0
            self.error_count = 0
            self.total_duration_ms = 0.0
            self.durable_write_failure_count = 0
            self.status_counts.clear()


runtime_metrics = RuntimeMetrics()


def record_request_metrics(
    settings: Settings,
    *,
    method: str,
    route_template: str,
    status_code: int,
    result_category: str,
    duration_ms: float,
) -> None:
    runtime_metrics.record(status_code=status_code, duration_ms=duration_ms)
    stored = record_request_metric(
        settings.metrics_database_path,
        method=method,
        route_template=route_template,
        status_code=status_code,
        result_category=result_category,
        duration_ms=duration_ms,
        latency_threshold_ms=settings.metrics_latency_threshold_ms,
        bucket_seconds=settings.metrics_bucket_seconds,
        retention_seconds=settings.metrics_retention_seconds,
    )
    if not stored:
        runtime_metrics.record_durable_write_failure()


def durable_metrics_snapshot(settings: Settings) -> dict[str, Any] | None:
    try:
        snapshot = metrics_snapshot(
            settings.metrics_database_path,
            window_seconds=settings.metrics_window_seconds,
            bucket_seconds=settings.metrics_bucket_seconds,
            retention_seconds=settings.metrics_retention_seconds,
            availability_slo_percent=settings.metrics_availability_slo_percent,
            latency_slo_percent=settings.metrics_latency_slo_percent,
            latency_threshold_ms=settings.metrics_latency_threshold_ms,
            alert_min_requests=settings.metrics_alert_min_requests,
        )
    except (OSError, sqlite3.Error, ValueError):
        return None
    process = runtime_metrics.snapshot()
    snapshot["collector"] = {
        "status": "ready",
        "process_uptime_seconds": process["uptime_seconds"],
        "current_worker_write_failures": process["durable_write_failure_count"],
    }
    return snapshot


def unavailable_metrics_snapshot() -> dict[str, Any]:
    process = runtime_metrics.snapshot()
    return {
        **process,
        "backend": "sqlite",
        "durable": False,
        "collector": {
            "status": "unavailable",
            "process_uptime_seconds": process["uptime_seconds"],
            "current_worker_write_failures": process["durable_write_failure_count"],
        },
        "slo": None,
        "alerts": [
            {
                "code": "metrics_backend_unavailable",
                "severity": "critical",
            }
        ],
    }
