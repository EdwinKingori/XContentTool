from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseResponse


class PostAnalyticsRead(BaseResponse):
    """
    Engagement metrics for a published post.

    All counters reflect the last values fetched from the X API by the
    generate_analytics Celery task.
    """

    id: UUID
    post_id: UUID
    impressions: int = Field(description="Times the tweet was displayed to X users.")
    likes: int
    retweets: int = Field(description="Direct retweets, not quote-tweets.")
    replies: int
    quotes: int = Field(description="Quote-tweets referencing this post.")
    link_clicks: int
    profile_visits: int
    last_fetched_at: datetime
    created_at: datetime
    updated_at: datetime
