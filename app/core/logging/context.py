from contextvars import ContextVar
from typing import Optional

# One ContextVar per piece of request-scoped context.
# ContextVars are async-safe: each asyncio Task (i.e. each request) gets its
# own copy, so there is no cross-request bleed even under heavy concurrency.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def get_request_id() -> str:
    return request_id_var.get()


def get_tenant_id() -> Optional[str]:
    return tenant_id_var.get()


def get_user_id() -> Optional[str]:
    return user_id_var.get()


def bind_request_context(
    request_id: str = "",
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Set all context vars for the current request/task scope."""
    request_id_var.set(request_id)
    tenant_id_var.set(tenant_id)
    user_id_var.set(user_id)


def clear_request_context() -> None:
    request_id_var.set("")
    tenant_id_var.set(None)
    user_id_var.set(None)
