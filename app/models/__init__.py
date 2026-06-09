# Register all ORM models against Base.metadata.
#
# Alembic's env.py imports this module so that every table is visible to
# autogenerate before it compares the metadata with the live database schema.
#
# Import order matters for SQLAlchemy's mapper configuration:
# - Base tables (no FKs) first, then dependent tables.
# - Models within the same file (e.g. Post + PostMedia) are registered together.

from app.models.tenant import Tenant  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.x_account import XAccount  # noqa: F401
from app.models.workbook import Workbook, WorkbookParseError  # noqa: F401
from app.models.post import Post, PostMedia  # noqa: F401
from app.models.analytics import PostAnalytics  # noqa: F401
