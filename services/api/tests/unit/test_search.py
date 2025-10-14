"""Testes para o endpoint de busca."""

from __future__ import annotations

import uuid

import pytest
from opensearchpy import OpenSearchException

from services.api.atlas_api.deps import CurrentUser, get_current_user, get_db
from services.api.atlas_api.routes import search as search_module


@pytest.fixture()
def authenticated_user(client: "TestClient") -> CurrentUser:
    user = CurrentUser(
        id=uuid.uuid4(),
        email="user@example.com",
        roles=["viewer"],
        organization_ids=[uuid.uuid4()],
    )

    async def fake_get_current_user() -> CurrentUser:
        return user

    async def fake_get_db():
        class _DummySession:  # pragma: no cover - apenas para tipagem
            ...

        yield _DummySession()

    overrides = client.app.dependency_overrides
    overrides[get_current_user] = fake_get_current_user
    overrides[get_db] = fake_get_db

    yield user

    overrides.pop(get_current_user, None)
    overrides.pop(get_db, None)


def test_search_uses_opensearch(client: "TestClient", authenticated_user: CurrentUser, monkeypatch: pytest.MonkeyPatch) -> None:
    expected_response = search_module.SearchResponse(
        results=[
            search_module.SearchResponseItem(
                id="1",
                title="Doc",
                snippet="Resumo",
                tags=["tag"],
            )
        ],
        total=1,
    )

    async def fake_search_database(*args, **kwargs):  # pragma: no cover - não deve ser chamado
        raise AssertionError("Fallback para banco não deveria ocorrer")

    def fake_search_opensearch(q: str, filter_tags: list[str], current_user: CurrentUser) -> search_module.SearchResponse:
        assert q == "foo"
        assert filter_tags == ["tag"]
        assert current_user.id == authenticated_user.id
        return expected_response

    monkeypatch.setattr(search_module, "_search_database", fake_search_database)
    monkeypatch.setattr(search_module, "_search_opensearch", fake_search_opensearch)

    response = client.get("/search?q=foo&tags=tag")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()


def test_search_fallbacks_to_database_on_opensearch_error(
    client: "TestClient", authenticated_user: CurrentUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected_response = search_module.SearchResponse(
        results=[
            search_module.SearchResponseItem(
                id="2",
                title="Outro Doc",
                snippet="Resumo",
                tags=[],
            )
        ],
        total=1,
    )

    async def fake_search_database(q: str, filter_tags: list[str], current_user: CurrentUser, session: object) -> search_module.SearchResponse:
        assert q == "bar"
        assert filter_tags == []
        assert current_user.id == authenticated_user.id
        return expected_response

    def fake_search_opensearch(*args, **kwargs):
        raise OpenSearchException("boom")

    monkeypatch.setattr(search_module, "_search_database", fake_search_database)
    monkeypatch.setattr(search_module, "_search_opensearch", fake_search_opensearch)

    response = client.get("/search?q=bar")

    assert response.status_code == 200
    assert response.json() == expected_response.model_dump()