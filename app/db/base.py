from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base inherited by every ORM model in the project."""
    pass


class UUIDPKMixin:
    """
    Adds a UUID primary key column named `id`.

    PostgreSQL stores it as a native UUID type (16 bytes), not a string.
    The default is generated in Python (uuid4) so the value is available
    immediately after instantiation, before any DB round-trip.
    """
    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        sort_order=-100,
    )


class TimestampMixin:
    """
    Adds `created_at` and `updated_at` audit columns.

    Both default to the DB server clock (func.now()) so they are consistent
    even when rows are inserted outside of the application layer.
    `updated_at` is refreshed automatically by SQLAlchemy on every UPDATE.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=100,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        sort_order=101,
    )
