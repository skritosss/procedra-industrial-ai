from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.auth import UserPublic, UserRole, _validate_email


class InvitationCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    full_name: str = Field(..., min_length=2, max_length=120)
    role: UserRole = "operator"
    project_ids: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Full name is required")
        return normalized

    @field_validator("project_ids")
    @classmethod
    def normalize_project_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 64 for value in normalized):
            raise ValueError("Invalid project identifier")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate project identifier")
        return normalized


class InvitationPublic(BaseModel):
    invitation_id: str
    email: str
    full_name: str
    role: UserRole
    project_ids: list[str]
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None


class InvitationCreatedResponse(BaseModel):
    invitation: InvitationPublic
    invitation_token: str


class InvitationAcceptRequest(BaseModel):
    invitation_token: str = Field(..., min_length=32, max_length=256)
    password: str = Field(..., min_length=8, max_length=128)


class AdminUserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AdminUserUpdateRequest":
        if self.role is None and self.is_active is None:
            raise ValueError("At least one user field must be supplied")
        return self


class UserListResponse(BaseModel):
    users: list[UserPublic]


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class ProjectPublic(BaseModel):
    project_id: str
    organization_id: str
    name: str
    is_default: bool
    created_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectPublic]


class ProjectMembersResponse(BaseModel):
    project_id: str
    users: list[UserPublic]


class AdminAuditEvent(BaseModel):
    event_id: str
    organization_id: str
    actor_user_id: str
    action: str
    target_type: str
    target_id: str
    details: dict[str, object]
    created_at: datetime


class AdminAuditResponse(BaseModel):
    events: list[AdminAuditEvent]


class AdminActionResponse(BaseModel):
    message: str
