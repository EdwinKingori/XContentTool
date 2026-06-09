from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.models.enums import PlanTier
from app.schemas.base import AppBaseModel, BaseResponse


class TenantCreate(AppBaseModel):
    """Fields required to provision a new tenant (superadmin operation)."""

    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe identifier, e.g. 'acme-corp'.",
    )
    plan_tier: PlanTier = Field(default=PlanTier.FREE)

    @field_validator("slug")
    @classmethod
    def slug_lowercase(cls, v: str) -> str:
        return v.lower()


class TenantRead(BaseResponse):
    """Full tenant record returned to authorised callers."""

    id: UUID
    name: str
    slug: str
    plan_tier: PlanTier
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenantUpdate(AppBaseModel):
    """
    Partial update for a tenant.

    Slug is intentionally excluded — renaming it would break any existing
    integrations or bookmarked URLs.
    """

    name: str | None = Field(default=None, min_length=2, max_length=255)
    plan_tier: PlanTier | None = None
    is_active: bool | None = None
