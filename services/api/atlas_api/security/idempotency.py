"""Suporte a idempotência baseada em Redis."""

import hashlib
from typing import cast

from fastapi import HTTPException, Request, Response
from redis import Redis

HEADER_KEY = "Idempotency-Key"


def _cache_key(user_id: str, key: str, body_hash: str) -> str:
    return f"idem:{user_id}:{key}:{body_hash}"


def _hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def extract_idempotency_key(request: Request) -> str:
    key = request.headers.get(HEADER_KEY)
    if not key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")
    return key


def remember_response(redis: Redis, cache_key: str, response: Response, ttl_seconds: int = 86_400) -> None:
    redis.setex(cache_key, ttl_seconds, response.body)


def get_cached_response(redis: Redis, cache_key: str) -> bytes | None:
    payload = redis.get(cache_key)
    if payload is not None:
        return cast(bytes, payload)
    return None


def idempotency_middleware(request: Request, redis: Redis, user_id: str) -> tuple[str, bytes]:
    key = extract_idempotency_key(request)
    body = cast(bytes, getattr(request, "_body", b""))
    hashed_body = _hash_body(body)
    cache_key = _cache_key(user_id, key, hashed_body)
    cached = get_cached_response(redis, cache_key)
    if cached:
        raise HTTPException(status_code=409, detail="Idempotent request already processed")
    return cache_key, body
