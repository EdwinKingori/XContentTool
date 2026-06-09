import json
import logging
import sys
from datetime import datetime, timezone
from logging import LogRecord
from typing import Any

from app.core.logging.context import get_request_id, get_tenant_id, get_user_id

# Fields copied onto every LogRecord by Python internals — we don't re-emit them.
_SKIP_FIELDS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName",
})


class JSONFormatter(logging.Formatter):
    """
    Emits one JSON object per log line.

    Every record always contains:
        timestamp, level, logger, message, module, function, line

    Context vars (request_id, tenant_id, user_id) are injected automatically
    when bound via bind_request_context().

    Any keys passed in logger.info(..., extra={...}) are merged in.
    """

    def format(self, record: LogRecord) -> str:
        record.message = record.getMessage()

        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Inject async-safe request context
        if request_id := get_request_id():
            entry["request_id"] = request_id
        if tenant_id := get_tenant_id():
            entry["tenant_id"] = tenant_id
        if user_id := get_user_id():
            entry["user_id"] = user_id

        # Merge caller-supplied extra fields
        for key, value in record.__dict__.items():
            if key not in _SKIP_FIELDS and not key.startswith("_"):
                entry[key] = value

        # Append formatted exception if present
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable format for local development (LOG_FORMAT=text)."""

    _FMT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    _DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATEFMT)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure the root logger once at application startup.

    Call this as the very first thing inside the FastAPI lifespan so that
    all subsequent loggers (SQLAlchemy, uvicorn, app code) inherit the config.
    """
    formatter: logging.Formatter = (
        JSONFormatter() if log_format == "json" else TextFormatter()
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level.upper())
    root.handlers.clear()
    root.addHandler(handler)

    # Uvicorn re-emits access logs — hand control back to our root handler
    logging.getLogger("uvicorn").handlers.clear()
    logging.getLogger("uvicorn").propagate = True
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = True

    # SQLAlchemy query echo: only when DEBUG is truly requested
    sa_level = logging.DEBUG if log_level.upper() == "DEBUG" else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(sa_level)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
