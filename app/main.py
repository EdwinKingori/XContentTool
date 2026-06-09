import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging.logs import setup_logging
from app.core.logging.middleware import LoggingMiddleware
from app.db.database import check_db_connection, init_db
from app.redis.redis_config import check_redis_connection, close_redis

settings = get_settings()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(
        "X-Automation Tool starting",
        extra={
            "event": "app_starting",
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
            "version": settings.APP_VERSION,
        },
    )
    await init_db()
    yield
    await close_redis()
    logger.info("X-Automation Tool shutdown complete", extra={"event": "app_shutdown"})


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-tenant SaaS content automation for X (Twitter)",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)


@app.get("/", tags=["System"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/health", tags=["System"])
async def health_status():
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()

    overall = "healthy" if (db_ok and redis_ok) else "degraded"

    return {
        "status": overall,
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": "OK!" if db_ok else "error!",
            "redis": "OK!" if redis_ok else "error!",
        },
    }
