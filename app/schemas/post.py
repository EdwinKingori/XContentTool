from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.models.enums import MediaType, PostStatus
from app.schemas.base import AppBaseModel, BaseResponse


class PostMediaRead(BaseResponse):
    """A single media file attached to a post."""

    id: UUID
    post_id: UUID
    storage_path: str
    media_type: MediaType
    file_size_bytes: int
    x_media_id: str | None = Field(
        default=None,
        description="Assigned by X after upload. NULL until the publisher runs.",
    )
    display_order: int


class PostCreate(AppBaseModel):
    """Fields required to schedule a new post via the API."""

    x_account_id: UUID
    content: str = Field(min_length=1, max_length=280)
    scheduled_at: datetime
    workbook_id: UUID | None = None

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Tweet content cannot be blank or whitespace only.")
        return v


class PostRead(BaseResponse):
    """Full post record returned on list and detail endpoints."""

    id: UUID
    tenant_id: UUID
    workbook_id: UUID | None
    x_account_id: UUID
    content: str
    scheduled_at: datetime
    status: PostStatus
    tweet_id: str | None = None
    published_at: datetime | None = None
    retry_count: int
    last_error: str | None = None
    media: list[PostMediaRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PostUpdate(AppBaseModel):
    """
    Partial update for a scheduled post.

    Business rules (e.g. only PENDING posts can be edited) are enforced
    in the service layer, not here.
    """

    x_account_id: UUID | None = None
    content: str | None = Field(default=None, min_length=1, max_length=280)
    scheduled_at: datetime | None = None
    status: PostStatus | None = Field(
        default=None,
        description="Only CANCELLED is accepted via the API.",
    )
