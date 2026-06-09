from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.tenant import Tenant


class XAccount(Base, UUIDPKMixin, TimestampMixin):
    """
    An X (Twitter) account linked to a tenant via OAuth 2.0.

    One tenant may link multiple X accounts (e.g. brand account + support account).
    Each Post is assigned to exactly one XAccount at scheduling time.

    Token fields hold Fernet-encrypted ciphertext — the encryption and
    decryption happens exclusively in app/utils/encryption.py (Phase 5).
    Never store or return plain-text tokens anywhere.
    """

    __tablename__ = "x_accounts"

    # Prevents the same X account being linked to the same tenant twice
    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "x_user_id", name="uq_x_accounts_tenant_x_user_id"
        ),
    )

    # Owning tenant
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Numeric user ID returned by the X API (stable, unlike handles which can change)
    x_user_id: Mapped[str] = mapped_column(sa.String(50), nullable=False, index=True)

    # @handle displayed to users; refreshed on token refresh
    x_handle: Mapped[str] = mapped_column(sa.String(50), nullable=False)

    # Display name shown on the X profile
    display_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)

    # Fernet-encrypted OAuth 2.0 access token (decrypted only inside the publisher)
    encrypted_access_token: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # Fernet-encrypted OAuth 2.0 refresh token (used to renew the access token)
    encrypted_refresh_token: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # When the access token expires; used by the refresh_x_token Celery task
    token_expires_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )

    # Set to False when OAuth is revoked or token refresh permanently fails
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.true(),
    )

    # ── Relationships ────────────────────────────────────────────────────────

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="x_accounts")

    # Posts scheduled to publish through this account
    posts: Mapped[list[Post]] = relationship("Post", back_populates="x_account")

    def __repr__(self) -> str:
        return f"<XAccount id={self.id} handle={self.x_handle!r} tenant={self.tenant_id}>"
