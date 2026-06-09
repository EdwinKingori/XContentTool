from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.post import Post


class PostAnalytics(Base, UUIDPKMixin, TimestampMixin):
    """
    Engagement metrics for a single published post.

    Created by the generate_analytics Celery task after a post reaches
    PUBLISHED status. The task polls the X API periodically and updates
    the counters in-place (no history — last known values only).

    Relationship: one-to-one with Post (post_id is UNIQUE).
    Deleting a post cascades and removes its analytics record.
    """

    __tablename__ = "post_analytics"

    # One analytics record per post — enforced by the UNIQUE constraint
    post_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Number of times the tweet was displayed to X users
    impressions: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )

    # Heart reactions
    likes: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )

    # Direct retweets (not quotes)
    retweets: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )

    # Direct replies to the tweet
    replies: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )

    # Quote-tweets referencing this post
    quotes: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )

    # Clicks on any URLs in the tweet body
    link_clicks: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )

    # Clicks on the author's profile from within the tweet card
    profile_visits: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )

    # Timestamp of the last X API poll that populated these numbers
    last_fetched_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )

    # ── Relationship ─────────────────────────────────────────────────────────

    post: Mapped[Post] = relationship("Post", back_populates="analytics")

    def __repr__(self) -> str:
        return (
            f"<PostAnalytics post={self.post_id} "
            f"impressions={self.impressions} likes={self.likes}>"
        )
