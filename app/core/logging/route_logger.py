import logging


def get_route_logger(name: str) -> logging.Logger:
    """
    Return a module-level logger that inherits the root handler configured
    by setup_logging().

    Usage:
        logger = get_route_logger(__name__)
        logger.info("workbook uploaded", extra={"workbook_id": str(wid)})

    The JSONFormatter automatically injects request_id / tenant_id from
    the current request context, so you never need to pass them manually.
    """
    return logging.getLogger(name)
