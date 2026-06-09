# Register all ORM models against Base.metadata.
# Alembic's env.py imports this module so autogenerate can detect every table.
#
# Add one import per model file as each is created (Phase 2+):
#   from app.models.tenant import Tenant       # noqa: F401
#   from app.models.user import User           # noqa: F401
#   from app.models.workbook import Workbook   # noqa: F401
#   from app.models.post import Post           # noqa: F401
