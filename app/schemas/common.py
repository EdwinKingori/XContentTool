from typing import Generic, TypeVar
from uuid import UUID

from app.schemas.base import AppBaseModel, BaseResponse

T = TypeVar("T")


class PaginatedResponse(BaseResponse, Generic[T]):
    """
    Standard envelope for paginated list endpoints.

    Usage in route return type annotation:
        PaginatedResponse[WorkbookRead]
    """
    items: list[T]
    total: int       # total matching records across all pages
    page: int        # current 1-based page number
    page_size: int   # number of items per page
    pages: int       # total number of pages


class MessageResponse(AppBaseModel):
    """Simple acknowledgement for operations that return no entity."""
    message: str


class UUIDResponse(AppBaseModel):
    """Returned when a resource is created and only its ID is needed."""
    id: UUID
