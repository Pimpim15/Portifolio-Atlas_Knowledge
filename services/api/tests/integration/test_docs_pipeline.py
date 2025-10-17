"""Integration tests bridging API document creation and worker processing."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from services.api.atlas_api import bootstrap as bootstrap_module
from services.api.atlas_api.db.models import Organization
from services.api.atlas_api.deps import CurrentUser, SessionLocal, get_current_user
from services.api.atlas_api.queue import publisher as queue_publisher
from services.worker.atlas_worker import run as worker_run


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
        roles=["admin", "editor"],
        organization_ids=[org_id],
    )

    overrides = client.app.dependency_overrides

    async def fake_current_user() -> CurrentUser:  # noqa: D401 - simple override
        return user

    overrides[get_current_user] = fake_current_user

    events: list[dict[str, Any]] = []

    def fake_send_message(payload: dict[str, Any]) -> bool:
        events.append(payload)
        return True

    monkeypatch.setattr(queue_publisher, "_send_message", fake_send_message)

    payload = {
        "title": "Guia de DR",
        "body": "Procedimentos de recuperação",
        "tags": ["dr"],
    }
    headers = {"Idempotency-Key": "doc-create-1"}

    response = client.post("/docs", json=payload, headers=headers)

    assert response.status_code == 200, response.json()
    assert events, "message should be enqueued"

    message = events[0]
    assert message["action"] == "index"
    document_payload = message["document"]
    assert document_payload["title"] == "Guia de DR"

    indexed: list[tuple[str, dict[str, Any]]] = []

    def fake_index_document(client: object, index: str, document_id: str, payload: dict[str, Any]) -> None:
        indexed.append((document_id, payload))

    monkeypatch.setattr(worker_run, "index_document", fake_index_document)

    worker_run._process_message(message, object(), attempt=1, max_attempts=5)

    assert indexed and indexed[0][0] == document_payload["id"]

    versions_response = client.get(f"/docs/{document_payload['id']}/versions", headers=headers)
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["title"] == payload["title"]

    replay_response = client.post("/docs", json=payload, headers=headers)
    assert replay_response.status_code == 200
    assert replay_response.json() == response.json()
    assert len(events) == 1, "idempotent replay should not enqueue again"

    update_payload = {
        "title": "Guia de DR Atualizado",
        "body": "Procedimentos de recuperação revisados",
        "tags": ["dr", "revisado"],
    }
    update_headers = {"Idempotency-Key": "doc-update-1"}
    update_response = client.put(
        f"/docs/{document_payload['id']}",
        json=update_payload,
        headers=update_headers,
    )

    assert update_response.status_code == 200
    updated_doc = update_response.json()
    assert updated_doc["version"] == 2
    assert len(events) == 2, "update should enqueue reindex message"

    versions_after_update = client.get(f"/docs/{document_payload['id']}/versions", headers=headers)
    assert versions_after_update.status_code == 200
    versions_list = versions_after_update.json()
    assert len(versions_list) == 2
    assert versions_list[0]["version"] == 2
    assert versions_list[1]["version"] == 1
    assert versions_list[0]["title"] == update_payload["title"]
    assert versions_list[1]["title"] == payload["title"]

    pre_reindex_events = len(events)
    reindex_response = client.post("/docs/reindex", headers=headers)
    assert reindex_response.status_code == 202
    job_payload = reindex_response.json()
    if job_payload["total_documents"]:
        assert job_payload["processed_documents"] == 0
        assert job_payload["status"] == "running"
        assert job_payload["pending_items"] == job_payload["total_documents"]
        assert job_payload["running_items"] == 0
        assert job_payload["success_items"] == 0
        assert job_payload["failed_items"] == 0
    else:  # pragma: no cover - defensive for empty datasets
        assert job_payload["status"] == "success"
        assert job_payload["pending_items"] == 0
        assert job_payload["running_items"] == 0
    assert len(events) == pre_reindex_events + job_payload["total_documents"]

    reindex_events = events[pre_reindex_events:]
    job_item_ids = {event.get("job_item_id") for event in reindex_events}
    assert all(event.get("job_id") == job_payload["id"] for event in reindex_events)
    assert None not in job_item_ids
    assert len(job_item_ids) == len(reindex_events)

    for event in reindex_events:
        worker_run._process_message(event, object(), attempt=1, max_attempts=5)

    reindex_list = client.get("/docs/reindex?limit=10&offset=0", headers=headers)
    assert reindex_list.status_code == 200, reindex_list.json()
    listed_jobs = reindex_list.json()
    matched_jobs = [job for job in listed_jobs if job["id"] == job_payload["id"]]
    assert matched_jobs, "reindex job should be listed"
    matched_job = matched_jobs[0]
    assert matched_job["processed_documents"] == matched_job["total_documents"]
    assert matched_job["status"] == "success"
    assert matched_job["success_items"] == matched_job["total_documents"]
    assert matched_job["pending_items"] == 0
    assert matched_job["failed_items"] == 0

    items_page = client.get(
        f"/docs/reindex/{job_payload['id']}/items?limit=1",
        headers=headers,
    )
    assert items_page.status_code == 200, items_page.json()
    page_payload = items_page.json()
    assert page_payload["items"], "should return at least one job item"
    first_item = page_payload["items"][0]
    assert first_item["job_id"] == job_payload["id"]
    assert first_item["status"] == "success"

    if page_payload.get("next_cursor"):
        next_page = client.get(
            f"/docs/reindex/{job_payload['id']}/items?limit=10&cursor={page_payload['next_cursor']}",
            headers=headers,
        )
        assert next_page.status_code == 200, next_page.json()
        next_payload = next_page.json()
        assert next_payload["items"], "cursor pagination should return remaining items"
        assert all(item["id"] != first_item["id"] for item in next_payload["items"])

    overrides.pop(get_current_user, None)