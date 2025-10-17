"""Fixtures globais."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from services.api.atlas_api.deps import get_redis
from services.api.atlas_api.main import create_app


class _InMemoryRedis:
    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def setex(self, key: str, _ttl: int, value: bytes | str) -> None:  # pragma: no cover - simple stub
        if isinstance(value, str):
            self._store[key] = value.encode("utf-8")
        else:
            self._store[key] = value

    def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    app = create_app()
    fake_redis = _InMemoryRedis()
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as test_client:
        yield test_client
