from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.core.settings import Settings


SESSION_COOKIE_NAME = "industrial_ai_session"
CSRF_COOKIE_NAME = "industrial_ai_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
AUTH_TRANSPORT_HEADER_NAME = "X-Auth-Transport"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def browser_cookie_transport_requested(request: Request) -> bool:
    return request.headers.get(AUTH_TRANSPORT_HEADER_NAME, "").strip().lower() == "cookie"


def set_browser_auth_cookies(
    response: Response,
    *,
    session_token: str,
    csrf_token: str,
    settings: Settings,
) -> None:
    secure = settings.deployment_mode == "production"
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_token,
        max_age=settings.auth_session_ttl_seconds,
        path="/",
        secure=secure,
        httponly=True,
        samesite="strict",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=settings.auth_session_ttl_seconds,
        path="/",
        secure=secure,
        httponly=False,
        samesite="strict",
    )


def clear_browser_auth_cookies(response: Response, settings: Settings) -> None:
    secure = settings.deployment_mode == "production"
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=False,
        samesite="strict",
    )


def csrf_request_is_valid(request: Request) -> bool:
    if request.method.upper() not in _UNSAFE_METHODS:
        return True
    if getattr(request.state, "auth_transport", None) != "cookie":
        return True
    session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_token = request.headers.get(CSRF_HEADER_NAME, "")
    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        return False
    from app.storage.auth_store import session_csrf_is_valid

    return session_csrf_is_valid(session_token, header_token)
