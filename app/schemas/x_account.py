from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseResponse


class XAccountRead(BaseResponse):
    """
    X account record returned to the client.

    Encrypted token fields are deliberately absent — raw token material
    must never leave the server boundary.
    """

    id: UUID
    tenant_id: UUID
    x_user_id: str = Field(description="Numeric X user ID assigned by the X platform.")
    x_handle: str = Field(description="Current @handle.")
    display_name: str
    is_active: bool
    token_expires_at: datetime = Field(
        description="When the OAuth token expires; used to surface re-auth prompts in the UI."
    )
    created_at: datetime
    updated_at: datetime
