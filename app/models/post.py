from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import MediaType, PostStatus

if TYPE_CHECKING:
    from app.models.analytics import PostAnalytics
    from app.models.tenant import Tenant
    from app.models.workbook import Workbook
    from app.models.x_account import XAccount


class Post(Base, UUIDPKMixin, TimestampMixin):
    """
    A single tweet to be published at a scheduled time.

    Posts are created in two ways:
      1. Automatically by the parse_workbook Celery task (workbook_id is set).
      2. Manually via the API by editors/admins (workbook_id is NULL).

    The Celery Beat scheduler queries for PENDING posts where scheduled_at <= NOW()
    and dispatches a publish_post task for each one.

    status transitions (see PostStatus enum for full diagram):
        PENDING → QUEUED → PUBLISHING → PUBLISHED
                                     ↘ FAILED
        PENDING → CANCELLED
    """

    __tablename__ = "posts"

    # Composite index on the three columns Beat queries together on every tick
    __table_args__ = (
        sa.Index(
            "ix_posts_tenant_status_scheduled_at",
            "tenant_id",
            "status",
            "scheduled_at",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # NULL for manually created posts; set for workbook-derived posts
    workbook_id: Mapped[Optional[UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workbooks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The X account this post will be published from
    x_account_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("x_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Tweet text — X enforces a 280-character limit at the API level
    content: Mapped[str] = mapped_column(sa.String(280), nullable=False)

    # Timezone-aware UTC timestamp for when the tweet should be published
    scheduled_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, index=True
    )

    # Current state in the publishing state machine
    status: Mapped[str] = mapped_column(
        sa.Enum(PostStatus, native_enum=False, length=20),
        nullable=False,
        default=PostStatus.PENDING,
        server_default=PostStatus.PENDING.value,
        index=True,
    )

    # Assigned by X after a successful publish; NULL until then
    tweet_id: Mapped[Optional[str]] = mapped_column(
        sa.String(50), nullable=True, index=True
    )

    # Exact time the tweet was confirmed published by the X API
    published_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Number of publish attempts made so far; used by the retry policy
    retry_count: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=0, server_default="0"
    )

    # Most recent error message from a failed publish attempt
    last_error: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="posts")

    # nullable because workbook_id is SET NULL when a workbook is deleted
    workbook: Mapped[Optional[Workbook]] = relationship(
        "Workbook", back_populates="posts"
    )

    x_account: Mapped[XAccount] = relationship("XAccount", back_populates="posts")

    # Media files attached to this tweet (up to 4 images or 1 video)
    # Ordered by display_order so the publisher sends them in the correct sequence
    media: Mapped[list[PostMedia]] = relationship(
        "PostMedia",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostMedia.display_order",
    )

    # One-to-one engagement metrics record; created after publishing
    analytics: Mapped[Optional[PostAnalytics]] = relationship(
        "PostAnalytics",
        back_populates="post",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Post id={self.id} status={self.status} scheduled_at={self.scheduled_at}>"
        )


class PostMedia(Base, UUIDPKMixin, TimestampMixin):
    """
    A single media file (image, video, or GIF) attached to a post.

    X allows up to 4 images or 1 video per tweet. display_order preserves the
    intended left-to-right sequence when multiple images are attached.

    x_media_id is assigned by X's media upload endpoint and is required when
    creating the tweet. It is NULL until the publisher uploads the file to X.
    """

    __tablename__ = "post_media"

    post_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Path on disk or object-store key where the media file is stored
    storage_path: Mapped[str] = mapped_column(sa.String(512), nullable=False)

    # Determines how the publisher handles the file (image vs video upload endpoint)
    media_type: Mapped[str] = mapped_column(
        sa.Enum(MediaType, native_enum=False, length=10),
        nullable=False,
    )

    # Raw file size used for storage billing and X upload validation
    file_size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    # Assigned by X after POST /2/media/upload; required when creating the tweet
    x_media_id: Mapped[Optional[str]] = mapped_column(
        sa.String(50), nullable=True
    )

    # 0-based position in the tweet's media array (0 = leftmost)
    display_order: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, default=0, server_default="0"
    )

    # ── Relationship ─────────────────────────────────────────────────────────

    post: Mapped[Post] = relationship("Post", back_populates="media")

    def __repr__(self) -> str:
        return (
            f"<PostMedia id={self.id} type={self.media_type} "
            f"order={self.display_order} post={self.post_id}>"
        )
