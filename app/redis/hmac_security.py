import hashlib
import hmac

from app.core.config import get_settings

settings = get_settings()


def hmac_key(key: str) -> str:
    """
    HMAC key signing for Redis.
    Return an HMAC-SHA256 digest of *key* using REDIS_HMAC_SECRET.

    Signs Redis key names with HMAC-SHA256 using REDIS_HMAC_SECRET
    to prevent key injection and namespace collisions.

    """
    return hmac.new(
        settings.REDIS_HMAC_SECRET.encode(),
        key.encode(),
        hashlib.sha256,
    ).hexdigest()