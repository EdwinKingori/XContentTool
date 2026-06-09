import logging

from sqlalchemy import text

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def check_db_connection() -> bool:
    """
    Ping the database with a cheap SELECT 1.
    Used by the /health endpoint to report DB status without a full query.
    Returns True if reachable, False on any error.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health check failed", extra={"error": str(exc)})
        return False


async def init_db() -> None:
    """
    Called once at application startup inside the FastAPI lifespan.

    Phase 1: verifies the connection is reachable.
    Phase 2+: Alembic runs migrations externally (alembic upgrade head).
              This function will grow to run a migration check or emit a
              warning if the schema is behind the current revision.
    """
    reachable = await check_db_connection()
    if reachable:
        logger.info("Database connection established", extra={"event": "db_ready"})
    else:
        logger.critical(
            "Cannot reach the database on startup — check DATABASE_URL",
            extra={"event": "db_unavailable"},
        )
