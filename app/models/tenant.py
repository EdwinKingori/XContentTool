from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import PlanTier

if TYPE_CHECKING:
    # Imported only for type-checking; avoids circular imports at runtime.
    from app.models.post import Post
    from app.models.user import User
    from app.models.workbook import Workbook
    from app.models.x_account import XAccount


class Tenant(Base, UUIDPKMixin, TimestampMixin):
    """
    Top-level organisational unit in the multi-tenant architecture.

    Every other entity (users, workbooks, posts) carries a tenant_id FK
    so that all queries can be scoped to a single tenant in one WHERE clause.
    Deleting a tenant cascades through the entire ownership tree.
    """

    __tablename__ = "tenants"

    # Human-readable organisation name shown on dashboards
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    # URL-safe identifier used in subdomain routing and API paths (e.g. "acme-corp")
    slug: Mapped[str] = mapped_column(
        sa.String(100), nullable=False, unique=True, index=True
    )

    # Subscription tier controls feature access in the business logic layer
    plan_tier: Mapped[str] = mapped_column(
        sa.Enum(PlanTier, native_enum=False, length=20),
        nullable=False,
        default=PlanTier.FREE,
        server_default=PlanTier.FREE.value,
    )

    # Soft-disable a tenant without deleting their data
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.true(),
    )

    # ── Relationships ────────────────────────────────────────────────────────

    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    x_accounts: Mapped[list[XAccount]] = relationship(
        "XAccount",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    workbooks: Mapped[list[Workbook]] = relationship(
        "Workbook",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    posts: Mapped[list[Post]] = relationship(
        "Post",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug!r} plan={self.plan_tier}>"
