"""Fixtures globais."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

if sys.platform.startswith("win"):
    # Windows default (Proactor) não é suportado pelo psycopg async.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./atlas_test.db"
os.environ["OPENSEARCH_STUB"] = "1"

from services.api.atlas_api.config import get_settings
from services.api.atlas_api.deps import get_redis
from services.api.atlas_api.main import create_app

get_settings.cache_clear()

_db_path = Path("atlas_test.db")
if _db_path.exists():
    _db_path.unlink()


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
