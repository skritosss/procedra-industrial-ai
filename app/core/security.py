from __future__ import annotations

import secrets

from fastapi import Request

from app.core.browser_auth import SESSION_COOKIE_NAME
from app.core.settings import get_settings


def api_auth_required(path: str) -> bool:
    if path in {"/api/auth/register", "/api/auth/login", "/api/auth/invitations/accept"}:
        return False
    return path.startswith("/api/") or path.startswith("/generated/keyframes/")


def request_is_authorized(request: Request) -> bool:
    expected_token = get_settings().api_access_token
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        if expected_token and secrets.compare_digest(token, expected_token):
            request.state.auth_transport = "static_bearer"
            return True
        from app.storage.auth_store import get_user_by_token

        user = get_user_by_token(token)
        if user is not None:
            request.state.current_user = user
            request.state.auth_transport = "bearer"
            return True
    session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if session_token:
        from app.storage.auth_store import get_user_by_token

        user = get_user_by_token(session_token)
        if user is not None:
            request.state.current_user = user
            request.state.auth_transport = "cookie"
            return True
    return not expected_token
