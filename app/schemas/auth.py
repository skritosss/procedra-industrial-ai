from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


UserRole = Literal["operator", "master", "technologist", "safety", "quality", "admin"]


class UserPublic(BaseModel):
    user_id: str
    organization_id: str = Field(default="legacy", min_length=1, max_length=64)
    project_id: str = Field(default="legacy", min_length=1, max_length=64)
    email: str = Field(..., min_length=3, max_length=254)
    full_name: str = Field(..., min_length=2, max_length=120)
    role: UserRole
    is_active: bool = True
    created_at: datetime

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class RegisterUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    full_name: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = "operator"
    organization_name: str | None = Field(default=None, min_length=2, max_length=120)

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

    @field_validator("organization_name")
    @classmethod
    def normalize_organization_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Organization name is required")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class AuthResponse(BaseModel):
    user: UserPublic
    access_token: str | None = None
    token_type: Literal["bearer", "cookie"] = "bearer"


class CurrentUserResponse(BaseModel):
    user: UserPublic


class AuthActionResponse(BaseModel):
    message: str


def _validate_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized:
        raise ValueError("Invalid email")
    local, _, domain = normalized.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Invalid email")
    return normalized
