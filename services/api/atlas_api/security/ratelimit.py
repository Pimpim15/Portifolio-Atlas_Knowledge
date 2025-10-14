"""Configuração de rate-limit."""

import os
from functools import lru_cache

from slowapi import Limiter  # type: ignore[import]
from slowapi.util import get_remote_address  # type: ignore[import]

from ..config import get_settings


@lru_cache(maxsize=1)
def init_rate_limiter() -> Limiter:
    settings = get_settings()
    storage_uri = str(settings.redis_url) if os.environ.get("REDIS_URL") else "memory://"
    return Limiter(key_func=get_remote_address, storage_uri=storage_uri, strategy="fixed-window")
