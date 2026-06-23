from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import os
from pathlib import Path
import sqlite3
from math import isfinite
from time import sleep, time
from typing import Any


METRICS_SCHEMA_VERSION = 1
_RESULT_CATEGORIES = frozenset(
    {"success", "client_error", "security_denied", "throttled", "server_error"}
)


def initialize_metrics_store(database_path: Path) -> None:
    with closing(_connect(database_path)) as connection:
        _apply_schema(connection)
        check = connection.execute("PRAGMA quick_check").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise ValueError("Metrics database integrity check failed")
    os.chmod(database_path, 0o600)


def metrics_store_is_ready(database_path: Path) -> bool:
    try:
        initialize_metrics_store(database_path)
    except (OSError, sqlite3.Error, ValueError):
        return False
    return True


def record_request_metric(
    database_path: Path,
    *,
    method: str,
    route_template: str,
    status_code: int,
    result_category: str,
    duration_ms: float,
    latency_threshold_ms: float,
    bucket_seconds: int,
    retention_seconds: int,
    now: float | None = None,
) -> bool:
    try:
        _record_request_metric(
            database_path,
            method=method,
            route_template=route_template,
            status_code=status_code,
            result_category=result_category,
            duration_ms=duration_ms,
            latency_threshold_ms=latency_threshold_ms,
            bucket_seconds=bucket_seconds,
            retention_seconds=retention_seconds,
            now=now,
        )
    except (OSError, sqlite3.Error, ValueError):
        return False
    return True


def _record_request_metric(
    database_path: Path,
    *,
    method: str,
    route_template: str,
    status_code: int,
    result_category: str,
    duration_ms: float,
    latency_threshold_ms: float,
    bucket_seconds: int,
    retention_seconds: int,
    now: float | None = None,
) -> None:
    normalized_method = method.upper()
    if not normalized_method.isalpha() or not 3 <= len(normalized_method) <= 10:
        raise ValueError("Invalid metrics method")
    if not route_template.startswith("/") and route_template != "<unmatched>":
        raise ValueError("Invalid metrics route template")
    if len(route_template) > 256 or any(char in route_template for char in ("?", "#", "\r", "\n")):
        raise ValueError("Invalid metrics route template")
    if not 100 <= status_code <= 599 or result_category not in _RESULT_CATEGORIES:
        raise ValueError("Invalid metrics result")
    if (
        not isfinite(duration_ms)
        or not isfinite(latency_threshold_ms)
        or duration_ms < 0
        or latency_threshold_ms <= 0
        or bucket_seconds < 1
        or retention_seconds < bucket_seconds
    ):
        raise ValueError("Invalid metrics aggregation settings")

    current = time() if now is None else now
    bucket_start = int(current // bucket_seconds) * bucket_seconds
    retention_cutoff = int((current - retention_seconds) // bucket_seconds) * bucket_seconds
    slow_request = int(duration_ms > latency_threshold_ms)
    with closing(_connect(database_path)) as connection:
        _apply_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                INSERT INTO request_metric_buckets (
                    bucket_start, method, route_template, status_code,
                    result_category, request_count, total_duration_ms,
                    max_duration_ms, slow_request_count
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT (
                    bucket_start, method, route_template, status_code, result_category
                ) DO UPDATE SET
                    request_count = request_count + 1,
                    total_duration_ms = total_duration_ms + excluded.total_duration_ms,
                    max_duration_ms = MAX(max_duration_ms, excluded.max_duration_ms),
                    slow_request_count = slow_request_count + excluded.slow_request_count
                """,
                (
                    bucket_start,
                    normalized_method,
                    route_template,
                    status_code,
                    result_category,
                    duration_ms,
                    duration_ms,
                    slow_request,
                ),
            )
            connection.execute(
                "DELETE FROM request_metric_buckets WHERE bucket_start < ?",
                (retention_cutoff,),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def metrics_snapshot(
    database_path: Path,
    *,
    window_seconds: int,
    bucket_seconds: int,
    retention_seconds: int,
    availability_slo_percent: float,
    latency_slo_percent: float,
    latency_threshold_ms: float,
    alert_min_requests: int,
    now: float | None = None,
) -> dict[str, Any]:
    current = time() if now is None else now
    cutoff = int((current - window_seconds) // bucket_seconds) * bucket_seconds
    with closing(_connect(database_path)) as connection:
        _apply_schema(connection)
        totals = connection.execute(
            """
            SELECT
                COALESCE(SUM(request_count), 0) AS request_count,
                COALESCE(SUM(CASE WHEN status_code >= 500 THEN request_count ELSE 0 END), 0) AS error_count,
                COALESCE(SUM(total_duration_ms), 0.0) AS total_duration_ms,
                COALESCE(MAX(max_duration_ms), 0.0) AS max_duration_ms,
                COALESCE(SUM(slow_request_count), 0) AS slow_request_count
            FROM request_metric_buckets
            WHERE bucket_start >= ?
            """,
            (cutoff,),
        ).fetchone()
        status_rows = connection.execute(
            """
            SELECT status_code, SUM(request_count) AS count
            FROM request_metric_buckets WHERE bucket_start >= ?
            GROUP BY status_code ORDER BY status_code
            """,
            (cutoff,),
        ).fetchall()
        result_rows = connection.execute(
            """
            SELECT result_category, SUM(request_count) AS count
            FROM request_metric_buckets WHERE bucket_start >= ?
            GROUP BY result_category ORDER BY result_category
            """,
            (cutoff,),
        ).fetchall()
        route_rows = connection.execute(
            """
            SELECT method, route_template, SUM(request_count) AS request_count,
                   SUM(CASE WHEN status_code >= 500 THEN request_count ELSE 0 END) AS error_count,
                   SUM(total_duration_ms) AS total_duration_ms,
                   MAX(max_duration_ms) AS max_duration_ms,
                   SUM(slow_request_count) AS slow_request_count
            FROM request_metric_buckets WHERE bucket_start >= ?
            GROUP BY method, route_template
            ORDER BY request_count DESC, method, route_template
            LIMIT 100
            """,
            (cutoff,),
        ).fetchall()

    request_count = int(totals["request_count"])
    error_count = int(totals["error_count"])
    slow_request_count = int(totals["slow_request_count"])
    total_duration_ms = float(totals["total_duration_ms"])
    availability = _percentage(request_count - error_count, request_count)
    latency_compliance = _percentage(request_count - slow_request_count, request_count)
    sufficient_data = request_count >= alert_min_requests
    availability_status = _slo_status(sufficient_data, availability, availability_slo_percent)
    latency_status = _slo_status(sufficient_data, latency_compliance, latency_slo_percent)
    alerts = []
    if availability_status == "breached":
        alerts.append(
            {
                "code": "availability_slo_breach",
                "severity": "critical",
                "actual_percent": availability,
                "target_percent": availability_slo_percent,
            }
        )
    if latency_status == "breached":
        alerts.append(
            {
                "code": "latency_slo_breach",
                "severity": "warning",
                "actual_percent": latency_compliance,
                "target_percent": latency_slo_percent,
            }
        )

    return {
        "backend": "sqlite",
        "durable": True,
        "schema_version": METRICS_SCHEMA_VERSION,
        "window_seconds": window_seconds,
        "window_started_at": datetime.fromtimestamp(cutoff, UTC).isoformat(),
        "retention_seconds": retention_seconds,
        "request_count": request_count,
        "error_count": error_count,
        "server_error_count": error_count,
        "average_duration_ms": round(total_duration_ms / request_count, 3) if request_count else 0.0,
        "max_duration_ms": round(float(totals["max_duration_ms"]), 3),
        "slow_request_count": slow_request_count,
        "status_counts": {str(row["status_code"]): int(row["count"]) for row in status_rows},
        "result_counts": {str(row["result_category"]): int(row["count"]) for row in result_rows},
        "routes": [_route_snapshot(row) for row in route_rows],
        "slo": {
            "minimum_requests": alert_min_requests,
            "availability": {
                "target_percent": availability_slo_percent,
                "actual_percent": availability,
                "status": availability_status,
            },
            "latency": {
                "target_percent": latency_slo_percent,
                "actual_percent": latency_compliance,
                "threshold_ms": latency_threshold_ms,
                "status": latency_status,
            },
        },
        "alerts": alerts,
    }


def reset_metrics_store(database_path: Path) -> None:
    with closing(_connect(database_path)) as connection:
        _apply_schema(connection)
        connection.execute("DELETE FROM request_metric_buckets")
        connection.commit()


def _connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    for attempt in range(20):
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            break
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 19:
                connection.close()
                raise
            sleep(0.05)
    return connection


def _apply_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics_schema (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            version INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO metrics_schema (singleton, version) VALUES (1, ?)",
        (METRICS_SCHEMA_VERSION,),
    )
    row = connection.execute("SELECT version FROM metrics_schema WHERE singleton = 1").fetchone()
    if row is None or int(row["version"]) != METRICS_SCHEMA_VERSION:
        raise ValueError("Unsupported metrics database schema")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS request_metric_buckets (
            bucket_start INTEGER NOT NULL,
            method TEXT NOT NULL,
            route_template TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            result_category TEXT NOT NULL CHECK (
                result_category IN ('success', 'client_error', 'security_denied', 'throttled', 'server_error')
            ),
            request_count INTEGER NOT NULL CHECK (request_count >= 1),
            total_duration_ms REAL NOT NULL CHECK (total_duration_ms >= 0),
            max_duration_ms REAL NOT NULL CHECK (max_duration_ms >= 0),
            slow_request_count INTEGER NOT NULL CHECK (slow_request_count >= 0),
            PRIMARY KEY (bucket_start, method, route_template, status_code, result_category)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_request_metric_buckets_time ON request_metric_buckets (bucket_start)"
    )
    connection.commit()


def _percentage(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100.0, 3)


def _slo_status(sufficient_data: bool, actual: float | None, target: float) -> str:
    if not sufficient_data or actual is None:
        return "insufficient_data"
    return "met" if actual >= target else "breached"


def _route_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    request_count = int(row["request_count"])
    return {
        "method": str(row["method"]),
        "route_template": str(row["route_template"]),
        "request_count": request_count,
        "server_error_count": int(row["error_count"]),
        "average_duration_ms": round(float(row["total_duration_ms"]) / request_count, 3),
        "max_duration_ms": round(float(row["max_duration_ms"]), 3),
        "slow_request_count": int(row["slow_request_count"]),
    }
