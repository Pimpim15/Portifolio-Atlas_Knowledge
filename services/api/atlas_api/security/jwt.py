"""Funções utilitárias para JWT."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from jose import jwt

from ..config import get_settings


def _base_payload(sub: str, *, jti: str | None = None, **extra: Any) -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "jti": jti or uuid4().hex,
        **extra,
    }
    return payload


def create_access_token(
    sub: str,
    email: str,
    roles: list[str] | None = None,
    organization_ids: list[str] | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    raw_audience = settings.jwt_audience
    if isinstance(raw_audience, list | tuple | set):
        audience: str | None = next(iter(raw_audience), None)
    else:
        audience = raw_audience
    exp = datetime.now(UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    token_id = uuid4().hex
    payload = _base_payload(
        sub,
        email=email,
        roles=roles or ["viewer"],
        org_ids=organization_ids or [],
        jti=token_id,
        aud=audience,
        exp=int(exp.timestamp()),
    )
    encoded = cast(str, jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm))
    return encoded, token_id


def create_refresh_token(sub: str) -> tuple[str, str]:
    settings = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=settings.refresh_token_ttl_minutes)
    token_id = uuid4().hex
    payload = _base_payload(sub, token_type="refresh", jti=token_id, exp=int(exp.timestamp()))
    encoded = cast(str, jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm))
    return encoded, token_id
