from typing import NoReturn

from fastapi import APIRouter, HTTPException, Request

from app.core.authorization import require_permission
from app.core.settings import get_settings
from app.schemas.admin import (
    AdminActionResponse,
    AdminAuditResponse,
    AdminUserUpdateRequest,
    InvitationCreateRequest,
    InvitationCreatedResponse,
    InvitationPublic,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectMembersResponse,
    ProjectPublic,
    UserListResponse,
)
from app.schemas.auth import UserPublic
from app.storage.admin_store import AdminConflict, AdminResourceNotFound


router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_context(request: Request):
    settings = get_settings()
    context = require_permission(request, "project:admin", settings)
    if context.user is None:
        raise HTTPException(status_code=401, detail="Active administrator session is required")
    return settings, context


def _raise_admin_error(exc: ValueError) -> NoReturn:
    if isinstance(exc, AdminResourceNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, AdminConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/invitations", response_model=InvitationCreatedResponse)
def invite_user(http_request: Request, request: InvitationCreateRequest) -> InvitationCreatedResponse:
    from app.storage.admin_store import create_invitation

    settings, context = _admin_context(http_request)
    try:
        invitation, token = create_invitation(
            context.organization_id,
            context.user.user_id,
            request.email,
            request.full_name,
            request.role,
            request.project_ids,
            ttl_seconds=settings.auth_invitation_ttl_seconds,
            database_path=settings.database_path,
        )
    except ValueError as exc:
        _raise_admin_error(exc)
    return InvitationCreatedResponse(invitation=invitation, invitation_token=token)


@router.get("/invitations", response_model=list[InvitationPublic])
def get_invitations(request: Request) -> list[InvitationPublic]:
    from app.storage.admin_store import list_invitations

    settings, context = _admin_context(request)
    return list_invitations(
        context.organization_id,
        context.user.user_id,
        database_path=settings.database_path,
    )


@router.delete("/invitations/{invitation_id}", response_model=AdminActionResponse)
def delete_invitation(invitation_id: str, request: Request) -> AdminActionResponse:
    from app.storage.admin_store import revoke_invitation

    settings, context = _admin_context(request)
    try:
        revoke_invitation(
            context.organization_id,
            context.user.user_id,
            invitation_id,
            database_path=settings.database_path,
        )
    except ValueError as exc:
        _raise_admin_error(exc)
    return AdminActionResponse(message="Invitation revoked")


@router.get("/users", response_model=UserListResponse)
def get_users(request: Request) -> UserListResponse:
    from app.storage.admin_store import list_organization_users

    settings, context = _admin_context(request)
    users = list_organization_users(
        context.organization_id,
        context.user.user_id,
        database_path=settings.database_path,
    )
    return UserListResponse(users=users)


@router.patch("/users/{user_id}", response_model=UserPublic)
def update_user(user_id: str, http_request: Request, request: AdminUserUpdateRequest) -> UserPublic:
    from app.storage.admin_store import update_organization_user

    settings, context = _admin_context(http_request)
    try:
        return update_organization_user(
            context.organization_id,
            context.user.user_id,
            user_id,
            role=request.role,
            is_active=request.is_active,
            database_path=settings.database_path,
        )
    except ValueError as exc:
        _raise_admin_error(exc)


@router.post("/projects", response_model=ProjectPublic)
def create_project(http_request: Request, request: ProjectCreateRequest) -> ProjectPublic:
    from app.storage.admin_store import create_organization_project

    settings, context = _admin_context(http_request)
    try:
        return create_organization_project(
            context.organization_id,
            context.user.user_id,
            request.name,
            database_path=settings.database_path,
        )
    except ValueError as exc:
        _raise_admin_error(exc)


@router.get("/projects", response_model=ProjectListResponse)
def get_projects(request: Request) -> ProjectListResponse:
    from app.storage.admin_store import list_organization_projects

    settings, context = _admin_context(request)
    projects = list_organization_projects(
        context.organization_id,
        context.user.user_id,
        database_path=settings.database_path,
    )
    return ProjectListResponse(projects=projects)


@router.put("/projects/{project_id}/members/{user_id}", response_model=AdminActionResponse)
def add_project_member(project_id: str, user_id: str, request: Request) -> AdminActionResponse:
    return _set_project_member(project_id, user_id, request, present=True)


@router.delete("/projects/{project_id}/members/{user_id}", response_model=AdminActionResponse)
def remove_project_member(project_id: str, user_id: str, request: Request) -> AdminActionResponse:
    return _set_project_member(project_id, user_id, request, present=False)


@router.get("/projects/{project_id}/members", response_model=ProjectMembersResponse)
def get_project_members(project_id: str, request: Request) -> ProjectMembersResponse:
    from app.storage.admin_store import list_project_members

    settings, context = _admin_context(request)
    try:
        users = list_project_members(
            context.organization_id,
            context.user.user_id,
            project_id,
            database_path=settings.database_path,
        )
    except ValueError as exc:
        _raise_admin_error(exc)
    return ProjectMembersResponse(project_id=project_id, users=users)


def _set_project_member(
    project_id: str,
    user_id: str,
    request: Request,
    *,
    present: bool,
) -> AdminActionResponse:
    from app.storage.admin_store import set_project_membership

    settings, context = _admin_context(request)
    try:
        changed = set_project_membership(
            context.organization_id,
            context.user.user_id,
            project_id,
            user_id,
            present=present,
            database_path=settings.database_path,
        )
    except ValueError as exc:
        _raise_admin_error(exc)
    action = "added" if present else "removed"
    return AdminActionResponse(message=f"Project member {action}" if changed else "Project membership unchanged")


@router.get("/audit", response_model=AdminAuditResponse)
def get_admin_audit(request: Request) -> AdminAuditResponse:
    from app.storage.admin_store import list_admin_audit_events

    settings, context = _admin_context(request)
    events = list_admin_audit_events(
        context.organization_id,
        context.user.user_id,
        database_path=settings.database_path,
    )
    return AdminAuditResponse(events=events)
