from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.workbook import Workbook


class User(Base, UUIDPKMixin, TimestampMixin):
    """
    An authenticated user belonging to exactly one tenant.

    Email is unique globally (not just per tenant) so that a single email
    address can only be registered once across the entire platform.
    Authentication looks up by email first, then resolves the tenant.

    hashed_password is never exposed in any Pydantic schema.
    """

    __tablename__ = "users"

    # Tenant this user belongs to
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Globally unique — one login per email address across all tenants
    email: Mapped[str] = mapped_column(
        sa.String(320),  # RFC 5321 max email length
        nullable=False,
        unique=True,
        index=True,
    )

    # bcrypt hash — never store or return plain-text passwords
    hashed_password: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    full_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    # Determines what the user can see and do within their tenant
    role: Mapped[str] = mapped_column(
        sa.Enum(UserRole, native_enum=False, length=20),
        nullable=False,
        default=UserRole.EDITOR,
        server_default=UserRole.EDITOR.value,
    )

    # Set to False to disable login without deleting the account
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.true(),
    )

    # Updated on every successful login; NULL until first login
    last_login_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # ── Relationships ────────────────────────────────────────────────────────

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="users")

    # Workbooks this user uploaded; SET NULL on user delete so workbooks survive
    workbooks: Mapped[list[Workbook]] = relationship(
        "Workbook", back_populates="uploader"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
