from contextlib import asynccontextmanager
import os
from pathlib import Path
import re
from time import perf_counter
from typing import AsyncIterator, Awaitable, Callable, cast

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from starlette.responses import Response as StarletteResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.documents import router as documents_router
from app.api.history import router as history_router
from app.api.instructions import router as instructions_router
from app.api.videos import router as videos_router
from app.core.errors import (
    error_response,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.authorization import (
    require_permission,
    require_resource_access,
)
from app.core.browser_auth import (
    SESSION_COOKIE_NAME,
    clear_browser_auth_cookies,
    csrf_request_is_valid,
)
from app.core.organization import LEGACY_ORGANIZATION_ID, organization_storage_path
from app.core.observability import (
    durable_metrics_snapshot,
    record_request_metrics,
    unavailable_metrics_snapshot,
)
from app.core.request_logging import emit_request_log, result_category, route_template
from app.core.rate_limit import check_rate_limit
from app.core.security import api_auth_required, request_is_authorized
from app.core.settings import Settings, get_settings


STATIC_DIR = Path(__file__).parent / "static"
GENERATED_DIR = Path(__file__).resolve().parents[1] / "generated"
KEYFRAMES_DIR = GENERATED_DIR / "keyframes"
INSTRUCTIONS_DIR = GENERATED_DIR / "instructions"
UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
DOCUMENTS_DIR = UPLOADS_DIR / "documents"
MAX_REQUEST_ID_LENGTH = 128
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'none'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self'; "
    "script-src-attr 'none'; "
    "style-src 'self'; "
    "style-src-attr 'none'; "
    "img-src 'self' data: blob:; "
    "font-src 'self'; "
    "media-src 'self' blob:; "
    "connect-src 'self'"
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    from app.storage.auth_store import database_is_ready
    from app.storage.instruction_history import initialize_instruction_storage
    from app.storage.metrics_store import metrics_store_is_ready

    settings = get_settings()
    if not database_is_ready(settings.database_path):
        raise RuntimeError("Authentication database is not ready")
    initialize_instruction_storage()
    metrics_store_is_ready(settings.metrics_database_path)
    yield


app = FastAPI(
    title="Procedra",
    description="AI service for generating structured manufacturing work instructions.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(instructions_router, prefix="/api")
app.include_router(videos_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
KEYFRAMES_DIR.mkdir(parents=True, exist_ok=True)
INSTRUCTIONS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

ExceptionHandler = Callable[[Request, Exception], StarletteResponse | Awaitable[StarletteResponse]]
app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, http_exception_handler))
app.add_exception_handler(RequestValidationError, cast(ExceptionHandler, validation_exception_handler))
app.add_exception_handler(Exception, cast(ExceptionHandler, unhandled_exception_handler))


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    request.state.request_id = _safe_request_id(request.headers.get("X-Request-ID"))
    request.state.route_template = route_template(request, app.router.routes, ROUTE_TEMPLATES)
    started_at = perf_counter()
    try:
        auth_required = api_auth_required(request.url.path)
        authorized = request_is_authorized(request) if auth_required else True
        if auth_required and not authorized:
            response = error_response(
                request=request,
                status_code=401,
                code="unauthorized",
                message="API access token is required",
            )
            if request.cookies.get(SESSION_COOKIE_NAME):
                clear_browser_auth_cookies(response, get_settings())
        elif not csrf_request_is_valid(request):
            response = error_response(
                request=request,
                status_code=403,
                code="csrf_failed",
                message="Valid CSRF protection is required for cookie-authenticated changes",
            )
        else:
            rate_limit = check_rate_limit(request)
            if rate_limit.status == "unavailable":
                response = error_response(
                    request=request,
                    status_code=503,
                    code="rate_limit_unavailable",
                    message="Rate-limit storage is unavailable. Please retry later.",
                )
                response.headers["Retry-After"] = "1"
            elif rate_limit.status == "limited":
                response = error_response(
                    request=request,
                    status_code=429,
                    code="rate_limited",
                    message="Too many requests. Please wait before retrying.",
                )
                if rate_limit.retry_after_seconds is not None:
                    response.headers["Retry-After"] = str(rate_limit.retry_after_seconds)
            else:
                response = await call_next(request)
                response.headers.setdefault("X-RateLimit-Remaining", str(rate_limit.remaining))
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        _record_metrics(request, status_code=500, duration_ms=duration_ms)
        request.state.error_category = "internal_error"
        emit_request_log(request, status=500, duration_ms=duration_ms)
        raise
    duration_ms = (perf_counter() - started_at) * 1000
    _record_metrics(request, status_code=response.status_code, duration_ms=duration_ms)
    emit_request_log(request, status=response.status_code, duration_ms=duration_ms)
    response.headers.setdefault("X-Request-ID", request.state.request_id)
    response.headers.setdefault("X-Response-Time-ms", f"{duration_ms:.2f}")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    if get_settings().deployment_mode == "production":
        # Production only. Demo mode serves plain HTTP on localhost, and browsers
        # cache HSTS aggressively, so sending it there would force https on
        # 127.0.0.1 for a year and break local development well beyond this run.
        # `preload` is deliberately omitted: leaving that list is difficult and
        # there is no domain to commit yet.
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    if request.url.path.startswith(("/api/auth/", "/api/admin/")):
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Pragma", "no-cache")
    return response


def _safe_request_id(header_value: str | None) -> str:
    if not header_value:
        return _random_hex()
    if len(header_value) > MAX_REQUEST_ID_LENGTH:
        return _random_hex()
    if any(char in header_value for char in ("\r", "\n")):
        return _random_hex()
    return header_value


def _random_hex() -> str:
    return os.urandom(16).hex()


def _record_metrics(request: Request, *, status_code: int, duration_ms: float) -> None:
    resolved_route = request.state.route_template
    if resolved_route == "<unmatched>":
        resolved_route = route_template(request)
    record_request_metrics(
        get_settings(),
        method=request.method,
        route_template=resolved_route,
        status_code=status_code,
        result_category=result_category(status_code),
        duration_ms=duration_ms,
    )


def _is_writable_directory(path: Path) -> bool:
    return path.exists() and path.is_dir() and os.access(path, os.W_OK)


@app.get("/", include_in_schema=False)
def web_app() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/generated/keyframes/{video_id}/{filename}", include_in_schema=False)
def legacy_keyframe(video_id: str, filename: str, request: Request) -> FileResponse:
    return _keyframe_response(request, LEGACY_ORGANIZATION_ID, video_id, filename)


@app.get("/generated/keyframes/{organization_id}/{video_id}/{filename}", include_in_schema=False)
def organization_keyframe(
    organization_id: str,
    video_id: str,
    filename: str,
    request: Request,
) -> FileResponse:
    return _keyframe_response(request, organization_id, video_id, filename)


def _keyframe_response(request: Request, organization_id: str, video_id: str, filename: str) -> FileResponse:
    if not re.fullmatch(r"[a-f0-9]{32}", video_id) or not re.fullmatch(r"frame_[0-9]{2}\.jpg", filename):
        raise HTTPException(status_code=404, detail="Keyframe not found")
    settings = get_settings()
    context = require_permission(request, "video:read", settings)
    if context.user is None and organization_id != LEGACY_ORGANIZATION_ID:
        raise HTTPException(status_code=401, detail="Authenticated user session is required for keyframes")
    if context.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Keyframe not found")
    frame_root = organization_storage_path(KEYFRAMES_DIR, organization_id)
    frame_path = frame_root / video_id / filename
    if not frame_path.is_file():
        raise HTTPException(status_code=404, detail="Keyframe not found")
    if context.user is None and organization_id == LEGACY_ORGANIZATION_ID:
        return FileResponse(
            frame_path,
            headers={"Cache-Control": "private, no-store", "Vary": "Authorization, X-Project-ID"},
        )
    require_resource_access(
        context,
        "video",
        video_id,
        database_path=settings.database_path,
    )
    return FileResponse(
        frame_path,
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Authorization, X-Project-ID",
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response) -> dict[str, object]:
    details = _readiness_details()
    if details["status"] == "degraded":
        response.status_code = 503
    return {"status": details["status"]}


@app.get("/ready/details")
def ready_details(request: Request, response: Response) -> dict[str, object]:
    if not _has_observability_access(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    details = _readiness_details()
    if details["status"] == "degraded":
        response.status_code = 503
    return details


def _readiness_details() -> dict[str, object]:
    from app.storage.auth_store import database_is_read_only
    from app.storage.metrics_store import metrics_store_is_read_only_ready

    settings = get_settings()
    generated_writable = _is_writable_directory(GENERATED_DIR)
    keyframes_writable = _is_writable_directory(KEYFRAMES_DIR)
    instructions_writable = _is_writable_directory(INSTRUCTIONS_DIR)
    uploads_writable = _is_writable_directory(UPLOADS_DIR)
    documents_writable = _is_writable_directory(DOCUMENTS_DIR)
    database_parent_writable = _is_writable_directory(settings.database_path.parent)
    database_ready = database_parent_writable and database_is_read_only(settings.database_path)
    metrics_database_ready = metrics_store_is_read_only_ready(settings.metrics_database_path)
    readiness_status = (
        "ready"
        if generated_writable
        and keyframes_writable
        and instructions_writable
        and uploads_writable
        and documents_writable
        and database_ready
        and metrics_database_ready
        else "degraded"
    )
    return {
        "status": readiness_status,
        "deployment_mode": settings.deployment_mode,
        "openai_enabled": settings.openai_enabled,
        "public_sources_enabled": settings.public_sources_enabled,
        "max_public_sources": settings.public_sources_max_results,
        "document_max_bytes": settings.document_max_bytes,
        "api_auth_enabled": bool(settings.api_access_token),
        "public_registration_enabled": settings.auth_public_registration_enabled,
        "role_self_assignment_enabled": settings.auth_allow_role_self_assignment,
        "auth_session_ttl_seconds": settings.auth_session_ttl_seconds,
        "auth_session_idle_timeout_seconds": settings.auth_session_idle_timeout_seconds,
        "auth_session_retention_seconds": settings.auth_session_retention_seconds,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_requests": settings.rate_limit_requests,
        "auth_rate_limit_requests": settings.auth_rate_limit_requests,
        "metrics_public_enabled": settings.metrics_public_enabled,
        "trust_proxy_headers": settings.trust_proxy_headers,
        "video_allowed_hosts": list(settings.video_allowed_hosts),
        "capabilities": _capability_details(settings),
        "generated_dir_writable": generated_writable,
        "keyframes_dir_writable": keyframes_writable,
        "instructions_dir_writable": instructions_writable,
        "uploads_dir_writable": uploads_writable,
        "documents_dir_writable": documents_writable,
        "database_parent_writable": database_parent_writable,
        "database_ready": database_ready,
        "metrics_database_ready": metrics_database_ready,
    }


def _capability_details(settings: Settings) -> dict[str, dict[str, object]]:
    openai_configured = bool(settings.openai_enabled and settings.openai_api_key)
    model_status = "configured_not_probed" if openai_configured else (
        "fallback_only" if not settings.openai_enabled else "misconfigured_fallback"
    )
    return {
        "model_generation": {
            "mode": model_status,
            "external_health": "not_probed",
        },
        "vision_analysis": {
            "mode": model_status,
            "external_health": "not_probed",
        },
        "public_source_catalog": {
            "enabled": settings.public_sources_enabled,
            "mode": "local_catalog" if settings.public_sources_enabled else "disabled",
        },
        "video_url_ingest": {
            "enabled": settings.deployment_mode == "demo" or bool(settings.video_allowed_hosts),
            "host_allowlist_configured": bool(settings.video_allowed_hosts),
        },
    }


@app.get("/metrics")
def metrics(request: Request, response: Response) -> dict:
    if not _has_observability_access(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    snapshot = durable_metrics_snapshot(get_settings())
    if snapshot is None:
        response.status_code = 503
        return unavailable_metrics_snapshot()
    return snapshot


def _has_observability_access(request: Request) -> bool:
    settings = get_settings()
    if settings.metrics_public_enabled and settings.deployment_mode == "demo":
        return True
    if not request_is_authorized(request):
        return False
    return bool(settings.api_access_token or getattr(request.state, "current_user", None))


ROUTE_TEMPLATES = tuple(app.openapi()["paths"]) + (
    "/generated/keyframes/{video_id}/{filename}",
    "/generated/keyframes/{organization_id}/{video_id}/{filename}",
)
