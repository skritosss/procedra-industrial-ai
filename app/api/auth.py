import secrets

from fastapi import APIRouter, HTTPException, Request, Response

from app.core.browser_auth import (
    SESSION_COOKIE_NAME,
    browser_cookie_transport_requested,
    clear_browser_auth_cookies,
    set_browser_auth_cookies,
)
from app.core.settings import get_settings
from app.schemas.admin import InvitationAcceptRequest
from app.schemas.auth import (
    AuthActionResponse,
    AuthResponse,
    CurrentUserResponse,
    LoginRequest,
    RegisterUserRequest,
    UserPublic,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict[str, object]:
    """Expose only the controls the unauthenticated login UI may offer."""
    settings = get_settings()
    allowed_roles = (
        ["operator", "master", "technologist", "safety", "quality", "admin"]
        if settings.auth_allow_role_self_assignment
        else ["operator"]
    )
    return {
        "public_registration_enabled": settings.auth_public_registration_enabled,
        "role_self_assignment_enabled": settings.auth_allow_role_self_assignment,
        "allowed_registration_roles": allowed_roles,
        "minimum_password_length": settings.auth_min_password_length,
    }


@router.post("/register", response_model=AuthResponse, response_model_exclude_none=True)
def register_user(http_request: Request, http_response: Response, request: RegisterUserRequest) -> AuthResponse:
    from app.storage.auth_store import create_bootstrap_user, create_user

    settings = get_settings()
    has_bootstrap_token = _has_static_access_token(http_request)
    if len(request.password) < settings.auth_min_password_length:
        raise HTTPException(
            status_code=400,
            detail=f"Password must contain at least {settings.auth_min_password_length} characters",
        )
    if has_bootstrap_token:
        if request.role != "admin":
            raise HTTPException(status_code=403, detail="The bootstrap account must have the admin role")
    if not settings.auth_public_registration_enabled and not has_bootstrap_token:
        raise HTTPException(status_code=403, detail="Public account registration is disabled")
    if (
        request.role != "operator"
        and not settings.auth_allow_role_self_assignment
        and not has_bootstrap_token
    ):
        raise HTTPException(status_code=403, detail="Privileged roles require trusted provisioning")
    try:
        if has_bootstrap_token:
            user = create_bootstrap_user(
                str(request.email),
                request.full_name,
                request.password,
                request.role,
                request.organization_name or f"{request.full_name.strip()} Organization",
            )
        else:
            user = create_user(
                email=str(request.email),
                full_name=request.full_name,
                password=request.password,
                role=request.role,
                organization_id="legacy",
            )
    except ValueError as exc:
        status_code = 403 if "Bootstrap registration" in str(exc) else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return _issue_auth_session(user, http_request, http_response)


@router.post("/invitations/accept", response_model=AuthResponse, response_model_exclude_none=True)
def accept_user_invitation(
    http_request: Request,
    http_response: Response,
    request: InvitationAcceptRequest,
) -> AuthResponse:
    from app.storage.admin_store import AdminConflict, AdminResourceNotFound, accept_invitation

    settings = get_settings()
    if len(request.password) < settings.auth_min_password_length:
        raise HTTPException(
            status_code=400,
            detail=f"Password must contain at least {settings.auth_min_password_length} characters",
        )
    try:
        user = accept_invitation(
            request.invitation_token,
            request.password,
            database_path=settings.database_path,
        )
    except AdminResourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AdminConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _issue_auth_session(user, http_request, http_response)


@router.post("/login", response_model=AuthResponse, response_model_exclude_none=True)
def login_user(http_request: Request, http_response: Response, request: LoginRequest) -> AuthResponse:
    from app.storage.auth_store import authenticate_user

    user = authenticate_user(email=str(request.email), password=request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _issue_auth_session(user, http_request, http_response)


def _issue_auth_session(user: UserPublic, request: Request, response: Response) -> AuthResponse:
    from app.storage.auth_store import create_browser_session, create_session

    settings = get_settings()
    if browser_cookie_transport_requested(request):
        session_token, csrf_token = create_browser_session(user.user_id)
        set_browser_auth_cookies(
            response,
            session_token=session_token,
            csrf_token=csrf_token,
            settings=settings,
        )
        auth_response = AuthResponse(user=user, token_type="cookie")
    else:
        token = create_session(user.user_id)
        auth_response = AuthResponse(user=user, access_token=token, token_type="bearer")
    request.state.current_user = user
    request.state.organization_id = user.organization_id
    request.state.project_id = user.project_id
    return auth_response


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(request: Request) -> CurrentUserResponse:
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return CurrentUserResponse(user=user)


@router.post("/logout", response_model=AuthActionResponse)
def logout_user(request: Request, response: Response) -> AuthActionResponse:
    from app.storage.auth_store import revoke_session

    user = getattr(request.state, "current_user", None)
    token = _active_session_token(request)
    if user is None or not token or not revoke_session(token):
        raise HTTPException(status_code=401, detail="Active user session is required")
    if getattr(request.state, "auth_transport", None) == "cookie":
        clear_browser_auth_cookies(response, get_settings())
    return AuthActionResponse(message="Session revoked")


@router.post("/logout-all", response_model=AuthActionResponse)
def logout_all_user_sessions(request: Request, response: Response) -> AuthActionResponse:
    from app.storage.auth_store import revoke_user_sessions

    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Active user session is required")
    revoked = revoke_user_sessions(user.user_id)
    if getattr(request.state, "auth_transport", None) == "cookie":
        clear_browser_auth_cookies(response, get_settings())
    return AuthActionResponse(message=f"Revoked sessions: {revoked}")


def _bearer_token(request: Request) -> str:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" else ""


def _active_session_token(request: Request) -> str:
    if getattr(request.state, "auth_transport", None) == "cookie":
        return request.cookies.get(SESSION_COOKIE_NAME, "")
    return _bearer_token(request)


def _has_static_access_token(request: Request) -> bool:
    expected_token = get_settings().api_access_token
    supplied_token = _bearer_token(request)
    return bool(expected_token and supplied_token and secrets.compare_digest(supplied_token, expected_token))
