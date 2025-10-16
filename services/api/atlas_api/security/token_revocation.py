"""Helpers for token revocation and blacklist management."""

from __future__ import annotations

from datetime import UTC, datetime

from redis import Redis

_REVOCATION_PREFIX = "auth:revoked"


def _revocation_key(jti: str) -> str:
    return f"{_REVOCATION_PREFIX}:{jti}"


def mark_token_revoked(redis: Redis, jti: str, expires_at_epoch: int) -> None:
    """Store the token identifier in Redis until it naturally expires."""

    ttl = expires_at_epoch - int(datetime.now(UTC).timestamp())
    if ttl <= 0:
        ttl = 1
    redis.setex(_revocation_key(jti), ttl, "1")


def is_token_revoked(redis: Redis, jti: str) -> bool:
    """Return True when the token identifier is already blacklisted."""

    return bool(redis.exists(_revocation_key(jti)))
