from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.models.enums import WorkbookStatus
from app.schemas.base import AppBaseModel, BaseResponse


class WorkbookParseErrorRead(BaseResponse):
    """A single cell-level validation failure from the parsing task."""

    id: UUID
    workbook_id: UUID
    row_number: int = Field(description="1-based row number as seen in Excel.")
    column_name: str
    error_message: str
    raw_value: str | None = None


class WorkbookRead(BaseResponse):
    """Full workbook record returned on list and detail endpoints."""

    id: UUID
    tenant_id: UUID
    uploaded_by: UUID | None = None
    filename: str
    file_size_bytes: int
    row_count: int | None = Field(default=None, description="NULL until parsing completes.")
    valid_row_count: int | None = Field(default=None, description="Rows that became Post records.")
    status: WorkbookStatus
    created_at: datetime
    updated_at: datetime


class WorkbookUploadResponse(AppBaseModel):
    """
    Immediate 202 response after a file is received.

    Parsing happens asynchronously — the client polls
    GET /workbooks/{id} to track the status transition.
    """

    id: UUID
    filename: str
    file_size_bytes: int
    status: WorkbookStatus
    message: str = "File received. Parsing will begin shortly."
