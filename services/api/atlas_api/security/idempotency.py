"""Suporte a idempotência baseada em Redis."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, cast

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from redis import Redis

HEADER_KEY = "Idempotency-Key"
DEFAULT_TTL_SECONDS = 86_400


def _cache_key(user_id: str, key: str, body_hash: str) -> str:
    return f"idem:{user_id}:{key}:{body_hash}"


def _hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def extract_idempotency_key(request: Request) -> str:
    key = request.headers.get(HEADER_KEY)
    if not key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")
    return key.strip()


def _load_cached_payload(redis: Redis, cache_key: str) -> dict[str, Any] | None:
    raw = cast(bytes | None, redis.get(cache_key))
    if raw is None:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, AttributeError):  # pragma: no cover - defensive
        return None
    if isinstance(payload, dict):
        return cast(dict[str, Any], payload)
    return None


@dataclass
class IdempotencyContext:
    """Mantém informações da requisição idempotente."""

    redis: Redis
    cache_key: str
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    cached_payload: dict[str, Any] | None = None

    def replay_if_available(self) -> Response | None:
        if not self.cached_payload:
            return None

        status_code = int(self.cached_payload.get("status", 200))
        body = self.cached_payload.get("body")

        if body is None or status_code == 204:
            return Response(status_code=status_code)

        return JSONResponse(content=body, status_code=status_code)

    def store_response(self, content: Any, status_code: int) -> None:
        payload = {
            "status": status_code,
            "body": jsonable_encoder(content),
        }
        self.redis.setex(self.cache_key, self.ttl_seconds, json.dumps(payload, default=str))


async def build_idempotency_context(request: Request, redis: Redis, user_id: str) -> IdempotencyContext:
    key = extract_idempotency_key(request)
    body_bytes = await request.body()
    hashed_body = _hash_body(body_bytes)
    cache_key = _cache_key(user_id, key, hashed_body)
    cached_payload = _load_cached_payload(redis, cache_key)
    return IdempotencyContext(redis=redis, cache_key=cache_key, cached_payload=cached_payload)
