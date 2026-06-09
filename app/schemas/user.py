from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.base import AppBaseModel, BaseResponse


class UserCreate(AppBaseModel):
    """
    Fields submitted when registering a new user.

    `password` is plain text here — it is hashed in the service layer before
    being persisted. It is never stored or returned in plain text.
    """

    email: EmailStr = Field(description="Must be globally unique across all tenants.")
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = Field(default=UserRole.EDITOR)

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()


class UserRead(BaseResponse):
    """
    User record returned to the client.

    hashed_password is deliberately absent — it must never appear in any
    API response regardless of the caller's role.
    """

    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserUpdate(AppBaseModel):
    """
    Partial profile or permission update.

    Email and password changes require dedicated endpoints with additional
    verification (current-password check, re-verify email) and are handled
    separately in the auth router.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
