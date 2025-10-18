"""Integration tests ensuring seeded documents appear without manual reindex."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient
from sqlalchemy import select

from services.api.atlas_api.main import create_app
from services.api.atlas_api.deps import CurrentUser, get_current_user, get_db, get_redis
from services.api.atlas_api.db.models import Membership, User


class _InMemoryRedis:
    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def setex(self, key: str, _ttl: int, value: bytes | str) -> None:
        if isinstance(value, str):
            self._store[key] = value.encode("utf-8")
        else:
            self._store[key] = value

    def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0


def _build_client() -> TestClient:
    os.environ.setdefault("OPENSEARCH_STUB", "1")
    app = create_app()
    app.dependency_overrides[get_redis] = lambda: _InMemoryRedis()
    async def _stub_current_user() -> CurrentUser:
        async for session in get_db():
            user = await session.scalar(select(User).where(User.email == "admin@acme.com"))
            if user is None:
                break

            memberships = await session.execute(select(Membership.org_id).where(Membership.user_id == user.id))
            org_ids = memberships.scalars().all()
            if not org_ids:
                break

            return CurrentUser(id=user.id, email=user.email, roles=["admin"], organization_ids=org_ids)

        raise RuntimeError("Seed user not found for integration test")

    app.dependency_overrides[get_current_user] = _stub_current_user
    return TestClient(app)


def test_search_returns_seeded_documents_without_manual_reindex() -> None:
    with _build_client() as client:
        response = client.get("/search")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    titles = {item["title"] for item in payload["results"]}
    assert any("Runbook" in title or "Backup" in title for title in titles)
