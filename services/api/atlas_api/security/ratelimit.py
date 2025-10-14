"""Configuração de rate-limit."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import get_settings


def init_rate_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(key_func=get_remote_address, storage_uri=str(settings.redis_url), strategy="fixed-window")
