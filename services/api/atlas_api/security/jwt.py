"""Funções utilitárias para JWT."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import jwt

from ..config import get_settings


def _base_payload(sub: str, **extra: Any) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        **extra,
    }
    return payload


def create_access_token(
    sub: str,
    email: str,
    roles: list[str] | None = None,
    organization_ids: list[str] | None = None,
) -> str:
    settings = get_settings()
    raw_audience = settings.jwt_audience
    if isinstance(raw_audience, list | tuple | set):
        audience: str | None = next(iter(raw_audience), None)
    else:
        audience = raw_audience
    exp = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = _base_payload(
        sub,
        email=email,
        roles=roles or ["viewer"],
        org_ids=organization_ids or [],
        aud=audience,
        exp=int(exp.timestamp()),
    )
    return cast(str, jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm))


def create_refresh_token(sub: str) -> str:
    settings = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=settings.refresh_token_ttl_minutes)
    payload = _base_payload(sub, token_type="refresh", exp=int(exp.timestamp()))
    return cast(str, jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm))
