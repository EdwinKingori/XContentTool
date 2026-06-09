import enum


class PlanTier(str, enum.Enum):
    """Subscription plan assigned to a tenant."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserRole(str, enum.Enum):
    """
    Role-based access levels within a tenant.

    owner   — full control, cannot be removed by other admins
    admin   — full control over users and content, cannot delete tenant
    editor  — create, edit, schedule posts; cannot manage users
    viewer  — read-only dashboard access
    """
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class WorkbookStatus(str, enum.Enum):
    """
    State machine for an uploaded Excel workbook.

    UPLOADING → PARSING → PARSED
                        ↘ FAILED
    """
    UPLOADING = "uploading"   # file is being received and stored
    PARSING = "parsing"       # Celery worker is reading rows
    PARSED = "parsed"         # all valid rows inserted as Post records
    FAILED = "failed"         # parse task failed; see WorkbookParseError rows


class PostStatus(str, enum.Enum):
    """
    State machine for a single scheduled post.

    PENDING → QUEUED → PUBLISHING → PUBLISHED
                               ↘ FAILED
    PENDING → CANCELLED
    """
    PENDING = "pending"       # stored, waiting for scheduled_at to arrive
    QUEUED = "queued"         # dispatched to Celery, not yet executed
    PUBLISHING = "publishing" # worker is actively calling the X API
    PUBLISHED = "published"   # tweet created successfully; tweet_id is set
    FAILED = "failed"         # max retries exhausted; last_error is set
    CANCELLED = "cancelled"   # manually cancelled before publishing


class MediaType(str, enum.Enum):
    """Type of media file attached to a post."""
    IMAGE = "image"
    VIDEO = "video"
    GIF = "gif"
