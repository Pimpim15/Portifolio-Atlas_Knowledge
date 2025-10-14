"""Integration tests bridging API document creation and worker processing."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi.testclient import TestClient

from services.api.atlas_api import bootstrap as bootstrap_module
from services.api.atlas_api.deps import CurrentUser, SessionLocal, get_current_user
from services.api.atlas_api.queue import publisher as queue_publisher
from services.api.atlas_api.db.models import Organization
from services.worker.atlas_worker import run as worker_run
from sqlalchemy import select


async def _fetch_org_id_async() -> uuid.UUID:
    await bootstrap_module.init_application()
    async with SessionLocal() as session:
        result = await session.execute(select(Organization.id).limit(1))
        row = result.first()
        if row is None:  # pragma: no cover - seed should always create org
            raise RuntimeError("Missing seed organization")
        return row[0]


def _fetch_org_id() -> uuid.UUID:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_fetch_org_id_async())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def test_create_document_flow_triggers_worker(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(bootstrap_module, "get_client", lambda: object())
    monkeypatch.setattr(bootstrap_module, "ensure_index_exists", lambda *args, **kwargs: None)

    org_id = _fetch_org_id()
    user = CurrentUser(
        id=uuid.uuid4(),
        email="editor@example.com",
        roles=["editor"],
        organization_ids=[org_id],
    )

    overrides = client.app.dependency_overrides

    async def fake_current_user() -> CurrentUser:  # noqa: D401 - simple override
        return user

    overrides[get_current_user] = fake_current_user

    events: list[dict[str, Any]] = []

    def fake_send_message(payload: dict[str, Any]) -> None:
        events.append(payload)

    monkeypatch.setattr(queue_publisher, "_send_message", fake_send_message)

    payload = {
        "title": "Guia de DR",
        "body": "Procedimentos de recuperação",
        "tags": ["dr"],
    }
    headers = {"Idempotency-Key": "doc-create-1"}

    response = client.post("/docs", json=payload, headers=headers)

    assert response.status_code == 200
    assert events, "message should be enqueued"

    message = events[0]
    assert message["action"] == "index"
    document_payload = message["document"]
    assert document_payload["title"] == "Guia de DR"

    indexed: list[tuple[str, dict[str, Any]]] = []

    def fake_index_document(client: object, index: str, document_id: str, payload: dict[str, Any]) -> None:
        indexed.append((document_id, payload))

    monkeypatch.setattr(worker_run, "index_document", fake_index_document)

    worker_run._process_message(message, object())

    assert indexed and indexed[0][0] == document_payload["id"]

    replay_response = client.post("/docs", json=payload, headers=headers)
    assert replay_response.status_code == 200
    assert replay_response.json() == response.json()
    assert len(events) == 1, "idempotent replay should not enqueue again"

    overrides.pop(get_current_user, None)