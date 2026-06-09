from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import WorkbookStatus

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.tenant import Tenant
    from app.models.user import User


class Workbook(Base, UUIDPKMixin, TimestampMixin):
    """
    An Excel (.xlsx) file uploaded by a user.

    After upload the file is stored (local disk or S3) and a parse_workbook
    Celery task is dispatched. The task reads every row, validates the required
    columns, and inserts a Post record for each valid row. Invalid rows produce
    WorkbookParseError records instead.

    status transitions:
        UPLOADING → (Celery task dispatched) → PARSING → PARSED
                                                        ↘ FAILED
    """

    __tablename__ = "workbooks"

    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The user who uploaded the file; SET NULL if that user is later deleted
    # so the workbook and its posts are not lost
    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Original filename as the user named it on their local machine
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    # Absolute path on disk or object-store key (e.g. /tenants/<id>/workbooks/<uuid>.xlsx)
    storage_path: Mapped[str] = mapped_column(sa.String(512), nullable=False)

    # Raw file size in bytes — displayed in the UI and used for storage billing
    file_size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    # Total data rows read from the file; NULL until parsing completes
    row_count: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)

    # Rows that passed validation and became Post records; NULL until parsing completes
    valid_row_count: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)

    # Current processing state (see WorkbookStatus enum for state-machine diagram)
    status: Mapped[str] = mapped_column(
        sa.Enum(WorkbookStatus, native_enum=False, length=20),
        nullable=False,
        default=WorkbookStatus.UPLOADING,
        server_default=WorkbookStatus.UPLOADING.value,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────────

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="workbooks")

    # nullable because uploaded_by is SET NULL on user delete
    uploader: Mapped[Optional[User]] = relationship("User", back_populates="workbooks")

    # Posts generated from the rows of this workbook
    posts: Mapped[list[Post]] = relationship(
        "Post",
        back_populates="workbook",
        cascade="all, delete-orphan",
    )

    # Row-level parse failures; kept for the user to review and fix their sheet
    parse_errors: Mapped[list[WorkbookParseError]] = relationship(
        "WorkbookParseError",
        back_populates="workbook",
        cascade="all, delete-orphan",
        order_by="WorkbookParseError.row_number",
    )

    def __repr__(self) -> str:
        return (
            f"<Workbook id={self.id} filename={self.filename!r} status={self.status}>"
        )


class WorkbookParseError(Base, UUIDPKMixin):
    """
    A single cell-level validation failure from the Excel parsing task.

    One row in the uploaded workbook can produce multiple errors (e.g. both
    the content column and the scheduled_at column fail). Each failure is its
    own record so the user can see exactly which cells need fixing.

    No TimestampMixin — these records are immutable write-once audit entries.
    created_at is not needed; the parent Workbook.created_at covers timing.
    """

    __tablename__ = "workbook_parse_errors"

    workbook_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("workbooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 1-based row number matching what the user sees in Excel
    row_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # Name of the column header that failed (e.g. "scheduled_at", "content")
    column_name: Mapped[str] = mapped_column(sa.String(100), nullable=False)

    # Human-readable explanation of why validation failed
    error_message: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # The raw cell value as text so the user can see exactly what was in the cell
    raw_value: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    # ── Relationship ─────────────────────────────────────────────────────────

    workbook: Mapped[Workbook] = relationship(
        "Workbook", back_populates="parse_errors"
    )

    def __repr__(self) -> str:
        return (
            f"<WorkbookParseError workbook={self.workbook_id} "
            f"row={self.row_number} col={self.column_name!r}>"
        )
