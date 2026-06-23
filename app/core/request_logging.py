from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import os
import re
import sys
from typing import Final, Iterable, Literal

from fastapi import Request
from starlette.routing import BaseRoute, Match


LOGGER_NAME: Final = "industrial_ai.request"
REQUEST_LOGGER = logging.getLogger(LOGGER_NAME)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SECRET = re.compile(
    r"(?i)(?:bearer\s+\S+|basic\s+\S+|sk-[A-Za-z0-9_-]+|"
    r"(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+)"
)
_JWT = re.compile(r"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_ERROR_CATEGORIES: Final = frozenset(
    {
        "bad_request",
        "conflict",
        "csrf_failed",
        "forbidden",
        "http_error",
        "internal_error",
        "not_found",
        "payload_too_large",
        "rate_limit_unavailable",
        "rate_limited",
        "unauthorized",
        "unsupported_media_type",
        "validation_error",
    }
)
ResultCategory = Literal["success", "client_error", "security_denied", "throttled", "server_error"]


class RequestJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "request_event", {})
        if not isinstance(event, dict):
            event = {}
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds")
        payload = {
            "timestamp": timestamp,
            "schema_version": 1,
            "service": "industrial-instruction-ai",
            "event": "http_request",
            "worker_pid": record.process,
            "request_id": _safe_log_identifier(event.get("request_id")),
            "actor_id": _safe_log_identifier(event.get("actor_id")),
            "organization_id": _safe_log_identifier(event.get("organization_id")),
            "project_id": _safe_log_identifier(event.get("project_id")),
            "method": _safe_method(event.get("method")),
            "route_template": _safe_route_template(event.get("route_template")),
            "duration_ms": _safe_duration(event.get("duration_ms")),
            "status": _safe_status(event.get("status")),
            "result_category": _safe_result_category(event.get("result_category")),
            "error_category": _safe_error_category(event.get("error_category")),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_request_logging() -> None:
    configured_pid = getattr(REQUEST_LOGGER, "_industrial_ai_configured_pid", None)
    if configured_pid == os.getpid() and REQUEST_LOGGER.handlers:
        return
    REQUEST_LOGGER.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(RequestJsonFormatter())
    REQUEST_LOGGER.addHandler(handler)
    REQUEST_LOGGER.setLevel(logging.INFO)
    REQUEST_LOGGER.propagate = False
    setattr(REQUEST_LOGGER, "_industrial_ai_configured_pid", os.getpid())


def emit_request_log(request: Request, *, status: int, duration_ms: float) -> None:
    configure_request_logging()
    user = getattr(request.state, "current_user", None)
    resolved_route = getattr(request.state, "route_template", None)
    if not resolved_route or resolved_route == "<unmatched>":
        resolved_route = route_template(request)
    event = {
        "request_id": getattr(request.state, "request_id", None),
        "actor_id": getattr(user, "user_id", None),
        "organization_id": getattr(request.state, "organization_id", None)
        or getattr(user, "organization_id", None),
        "project_id": getattr(request.state, "project_id", None) or getattr(user, "project_id", None),
        "method": request.method,
        "route_template": resolved_route,
        "duration_ms": duration_ms,
        "status": status,
        "result_category": result_category(status),
        "error_category": getattr(request.state, "error_category", None),
    }
    REQUEST_LOGGER.info("http_request", extra={"request_event": event})


def route_template(
    request: Request,
    routes: Iterable[BaseRoute] | None = None,
    templates: Iterable[str] = (),
) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return _prefixed_route_template(request.url.path, route, path)
    candidates = routes if routes is not None else request.app.router.routes
    for candidate in candidates:
        match, child_scope = candidate.matches(request.scope)
        if match in {Match.FULL, Match.PARTIAL}:
            template = child_scope.get("route")
            candidate_path = getattr(template, "path", None) or getattr(candidate, "path", None)
            if isinstance(candidate_path, str):
                return candidate_path
    for template in templates:
        if _template_matches(request.url.path, template):
            return template
    return "<unmatched>"


def _prefixed_route_template(actual_path: str, route: object, template: str) -> str:
    route_regex = getattr(route, "path_regex", None)
    if route_regex is None or route_regex.fullmatch(actual_path):
        return template
    for index, char in enumerate(actual_path):
        if char == "/" and route_regex.fullmatch(actual_path[index:]):
            return actual_path[:index] + template
    return template


def _template_matches(path: str, template: str) -> bool:
    segments = []
    for segment in template.strip("/").split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            segments.append(".+" if segment.endswith(":path}") else "[^/]+")
        else:
            segments.append(re.escape(segment))
    pattern = "/" + "/".join(segments) if segments else "/"
    return re.fullmatch(pattern, path) is not None


def result_category(status: int) -> ResultCategory:
    if status < 400:
        return "success"
    if status in {401, 403}:
        return "security_denied"
    if status == 429:
        return "throttled"
    if status >= 500:
        return "server_error"
    return "client_error"


def _safe_log_identifier(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not _SAFE_IDENTIFIER.fullmatch(text):
        return "[redacted]"
    if _EMAIL.search(text) or _SECRET.search(text) or _JWT.search(text):
        return "[redacted]"
    return text


def _safe_method(value: object) -> str:
    text = str(value).upper()
    return text if re.fullmatch(r"[A-Z]{3,10}", text) else "UNKNOWN"


def _safe_route_template(value: object) -> str:
    text = str(value)
    if text == "<unmatched>":
        return text
    if len(text) <= 256 and text.startswith("/") and not any(char in text for char in ("?", "#", "\r", "\n")):
        return text
    return "<unmatched>"


def _safe_duration(value: object) -> float:
    if not isinstance(value, (int, float, str)):
        return 0.0
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(duration, 86_400_000.0)), 3)


def _safe_status(value: object) -> int:
    if not isinstance(value, (int, str)):
        return 500
    try:
        status = int(value)
    except (TypeError, ValueError):
        return 500
    return status if 100 <= status <= 599 else 500


def _safe_result_category(value: object) -> str:
    text = str(value)
    return text if text in {"success", "client_error", "security_denied", "throttled", "server_error"} else "server_error"


def _safe_error_category(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text in _ERROR_CATEGORIES else "internal_error"


configure_request_logging()
