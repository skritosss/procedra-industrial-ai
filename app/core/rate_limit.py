from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Literal
from ipaddress import ip_address

from fastapi import Request

from app.core.settings import get_settings
from app.storage.database import apply_migrations, connect_database


_EXPENSIVE_PATH_PREFIXES = (
    "/api/instructions/generate",
    "/api/instructions/generate-with-context",
    "/api/instructions/generate-from-video",
    "/api/instructions/export-pdf",
    "/api/videos/",
    "/api/documents/upload",
)
_AUTH_PATHS = {"/api/auth/register", "/api/auth/login", "/api/auth/invitations/accept"}
RateLimitStatus = Literal["allowed", "limited", "unavailable", "not_applicable"]


@dataclass(frozen=True)
class RateLimitDecision:
    status: RateLimitStatus
    remaining: int
    retry_after_seconds: int | None = None

    @property
    def allowed(self) -> bool:
        return self.status in {"allowed", "not_applicable"}


def reset_rate_limit_state(database_path: Path | None = None) -> None:
    settings = get_settings()
    path = database_path or settings.database_path
    with connect_database(path) as connection:
        apply_migrations(connection)
        connection.execute("DELETE FROM rate_limit_events")


def rate_limit_applies(request: Request) -> bool:
    if request.method not in {"POST", "PATCH"}:
        return False
    return request.url.path in _AUTH_PATHS or any(
        request.url.path.startswith(prefix) for prefix in _EXPENSIVE_PATH_PREFIXES
    )


def check_rate_limit(request: Request) -> RateLimitDecision:
    settings = get_settings()
    if not settings.rate_limit_enabled or not rate_limit_applies(request):
        return RateLimitDecision("not_applicable", settings.rate_limit_requests)
    if request.url.path in _AUTH_PATHS:
        limit = settings.auth_rate_limit_requests
        window = settings.auth_rate_limit_window_seconds
    else:
        limit = settings.rate_limit_requests
        window = settings.rate_limit_window_seconds
    try:
        return _consume_bucket(
            settings.database_path,
            _bucket_hash(_client_key(request)),
            limit=limit,
            window_seconds=window,
            cleanup_window_seconds=max(
                settings.rate_limit_window_seconds,
                settings.auth_rate_limit_window_seconds,
            ),
        )
    except (OSError, sqlite3.Error, ValueError):
        return RateLimitDecision("unavailable", 0)


def _consume_bucket(
    database_path: Path,
    bucket_hash: str,
    *,
    limit: int,
    window_seconds: int,
    cleanup_window_seconds: int,
    now: float | None = None,
) -> RateLimitDecision:
    current = time() if now is None else now
    cutoff = current - window_seconds
    with connect_database(database_path) as connection:
        apply_migrations(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                "DELETE FROM rate_limit_events WHERE occurred_at <= ?",
                (current - cleanup_window_seconds,),
            )
            rows = connection.execute(
                """
                SELECT occurred_at FROM rate_limit_events
                WHERE bucket_hash = ? AND occurred_at > ?
                ORDER BY occurred_at
                """,
                (bucket_hash, cutoff),
            ).fetchall()
            if len(rows) >= limit:
                retry_after = max(1, int(float(rows[0]["occurred_at"]) + window_seconds - current + 0.999))
                connection.commit()
                return RateLimitDecision("limited", 0, retry_after)
            connection.execute(
                "INSERT INTO rate_limit_events (bucket_hash, occurred_at) VALUES (?, ?)",
                (bucket_hash, current),
            )
            connection.commit()
            return RateLimitDecision("allowed", limit - len(rows) - 1)
        except Exception:
            connection.rollback()
            raise


def _bucket_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _client_key(request: Request) -> str:
    settings = get_settings()
    user = getattr(request.state, "current_user", None)
    user_id = getattr(user, "user_id", "")
    if user_id:
        return f"user:{user_id}:{_bucket_scope(request.url.path)}"
    client_ip = ""
    peer_ip = request.client.host if request.client else ""
    if settings.trust_proxy_headers and peer_ip in settings.trusted_proxy_ips:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        candidate = forwarded_for.split(",", 1)[0].strip()
        try:
            client_ip = str(ip_address(candidate))
        except ValueError:
            client_ip = ""
    if not client_ip:
        client_ip = peer_ip
    return f"{client_ip or 'unknown'}:{_bucket_scope(request.url.path)}"


def _bucket_scope(path: str) -> str:
    if path in _AUTH_PATHS:
        return path
    for prefix in _EXPENSIVE_PATH_PREFIXES:
        if path.startswith(prefix):
            return prefix
    return path
