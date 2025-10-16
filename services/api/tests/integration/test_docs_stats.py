"""Tests for the /docs/stats analytics endpoint."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from services.api.atlas_api import bootstrap as bootstrap_module
from services.api.atlas_api.db.models import Membership, Organization, RoleEnum, User
from services.api.atlas_api.deps import CurrentUser, SessionLocal, get_current_user
from services.api.atlas_api.queue import publisher as queue_publisher
from services.api.atlas_api.security.passwords import hash_password


async def _init_seed_data_async() -> tuple[uuid.UUID, uuid.UUID, str]:
    await bootstrap_module.init_application()
    async with SessionLocal() as session:
        org_result = await session.execute(select(Organization.id).limit(1))
        org_row = org_result.first()
        if org_row is None:
            raise RuntimeError("Seed organization not created")

        user_result = await session.execute(select(User.id, User.email).limit(1))
        user_row = user_result.first()
        if user_row is None:
            raise RuntimeError("Seed user not created")
        return org_row[0], user_row[0], user_row[1]


def _init_seed_data() -> tuple[uuid.UUID, uuid.UUID, str]:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_init_seed_data_async())
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _create_user_async(org_id: uuid.UUID, email: str, role: RoleEnum) -> uuid.UUID:
    async with SessionLocal() as session:
        user = User(id=uuid.uuid4(), email=email, password_hash=hash_password("changeme"), is_active=True)
        session.add(user)
        session.add(Membership(user_id=user.id, org_id=org_id, role=role))
        await session.commit()
        return user.id


def _create_user(org_id: uuid.UUID, email: str, role: RoleEnum) -> uuid.UUID:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_create_user_async(org_id, email, role))
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def test_docs_stats_returns_aggregated_metrics(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(bootstrap_module, "get_client", lambda: object())
    monkeypatch.setattr(bootstrap_module, "ensure_index_exists", lambda *args, **kwargs: None)
    monkeypatch.setattr(queue_publisher, "_send_message", lambda payload: None)

    org_id, seed_user_id, seed_email = _init_seed_data()

    initial_user = CurrentUser(
        id=seed_user_id,
        email=seed_email,
        roles=["admin", "editor"],
        organization_ids=[org_id],
    )

    overrides = client.app.dependency_overrides

    async def _user_one() -> CurrentUser:
        return initial_user

    overrides[get_current_user] = _user_one

    baseline_response = client.get("/docs/stats")
    assert baseline_response.status_code == 200, baseline_response.text
    baseline_payload = baseline_response.json()

    base_totals = baseline_payload["totals"]
    base_docs_total = base_totals["documents"]
    base_active_authors = base_totals["active_authors"]
    base_tag_counts = {entry["tag"]: entry["count"] for entry in baseline_payload["top_tags"]}
    base_author_counts = {entry["display_name"]: entry["count"] for entry in baseline_payload["top_authors"]}
    base_series_map = {point["date"]: point["count"] for point in baseline_payload["documents_by_day"]}

    headers: dict[str, Any] = {"Idempotency-Key": "stats-doc-1"}
    payloads = [
        {"title": "Runbook de Incidentes", "body": "Procedimentos P1", "tags": ["runbook", "incidentes"]},
        {"title": "Plano de Backup", "body": "Checklist RDS", "tags": ["runbook"]},
    ]

    for idx, payload in enumerate(payloads, start=1):
        headers["Idempotency-Key"] = f"stats-doc-{idx}"
        response = client.post("/docs", json=payload, headers=headers)
        assert response.status_code == 200, response.text

    second_user_email = f"alice-{uuid.uuid4().hex[:8]}@example.com"
    second_user_id = _create_user(org_id, second_user_email, RoleEnum.EDITOR)
    second_user = CurrentUser(
        id=second_user_id,
        email=second_user_email,
        roles=["editor"],
        organization_ids=[org_id],
    )

    async def _user_two() -> CurrentUser:
        return second_user

    overrides[get_current_user] = _user_two

    headers["Idempotency-Key"] = "stats-doc-3"
    third_payload = {
        "title": "Guia Zero Trust",
        "body": "Controles de acesso e segmentação",
        "tags": ["runbook", "seguranca"],
    }
    response = client.post("/docs", json=third_payload, headers=headers)
    assert response.status_code == 200, response.text

    overrides[get_current_user] = _user_one
    stats_response = client.get("/docs/stats")
    assert stats_response.status_code == 200, stats_response.text
    payload = stats_response.json()

    assert payload["totals"]["documents"] == base_docs_total + 3
    assert payload["totals"]["active_authors"] >= base_active_authors + 1

    def _author_count(entries: list[dict[str, Any]], email: str) -> int:
        return next((entry["count"] for entry in entries if entry["display_name"] == email), 0)

    def _tag_count(entries: list[dict[str, Any]], tag: str) -> int:
        return next((entry["count"] for entry in entries if entry["tag"] == tag), 0)

    assert _tag_count(payload["top_tags"], "runbook") >= base_tag_counts.get("runbook", 0) + 3
    assert _tag_count(payload["top_tags"], "incidentes") >= base_tag_counts.get("incidentes", 0) + 1

    assert _author_count(payload["top_authors"], seed_email) >= base_author_counts.get(seed_email, 0) + 2

    assert payload["documents_by_day"]
    series_map = {point["date"]: point["count"] for point in payload["documents_by_day"]}

    recent_entries = [doc for doc in payload["recent_documents"] if doc["title"] == third_payload["title"]]
    assert recent_entries, "Expected the most recent document to appear in the recent list"
    assert recent_entries[0]["author"] == second_user_email
    assert "seguranca" in recent_entries[0]["tags"]

    created_dt = datetime.fromisoformat(recent_entries[0]["created_at"].replace("Z", "+00:00"))
    created_date_key = created_dt.date().isoformat()
    assert series_map.get(created_date_key, 0) >= base_series_map.get(created_date_key, 0) + 3

    overrides.pop(get_current_user, None)
