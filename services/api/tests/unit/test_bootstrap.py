"""Tests for bootstrap helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from services.api.atlas_api import bootstrap
from services.api.atlas_api.db.models import Document


def _sample_document() -> Document:
    now = datetime.utcnow()
    return Document(
        org_id=uuid.uuid4(),
        title="Seed Doc",
        body="Conteúdo inicial",
        tags=["seed"],
        created_by=uuid.uuid4(),
        updated_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def test_index_seed_documents_enqueues(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _sample_document()
    enqueued: list[Document] = []

    def fake_enqueue(doc: Document) -> None:
        enqueued.append(doc)

    monkeypatch.setattr(bootstrap, "enqueue_document", fake_enqueue)

    bootstrap._index_seed_documents([document])

    assert enqueued == [document]


def test_index_seed_documents_ignores_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_enqueue(_doc: Document) -> None:  # pragma: no cover - should not run
        raise AssertionError("enqueue should not be called")

    monkeypatch.setattr(bootstrap, "enqueue_document", fail_enqueue)

    bootstrap._index_seed_documents([])