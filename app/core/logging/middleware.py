import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging.context import bind_request_context, clear_request_context

logger = logging.getLogger("app.request")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that wraps every HTTP request with structured logging.

    Per request it:
      1. Generates a UUID request_id and binds it to the context vars
         (so every downstream log line carries the same request_id).
      2. Logs request start: method, path, client IP.
      3. Logs request end: status code, duration in ms.
      4. Returns the response with an X-Request-ID header so callers can
         correlate their client-side logs with server-side logs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        bind_request_context(request_id=request_id)

        client_host = request.client.host if request.client else "unknown"

        logger.info(
            "Request started",
            extra={
                "event": "request_start",
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query) or None,
                "client_ip": client_host,
            },
        )

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "Request failed with unhandled exception",
                extra={
                    "event": "request_error",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            clear_request_context()
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "Request completed",
            extra={
                "event": "request_end",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        clear_request_context()
        return response
