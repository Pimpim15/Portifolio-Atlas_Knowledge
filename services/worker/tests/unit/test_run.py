"""Unit tests for the worker poller logic."""

from __future__ import annotations

from typing import Any

import pytest

from services.worker.atlas_worker import run


@pytest.fixture()
def fake_os_client() -> dict[str, Any]:
    return {}


def test_process_message_index(monkeypatch: pytest.MonkeyPatch, fake_os_client: dict[str, Any]) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_index_document(client: Any, index: str, document_id: str, payload: dict[str, Any]) -> None:  # noqa: ANN401
        calls.append((document_id, payload))

    monkeypatch.setattr(run, "index_document", fake_index_document)

    body = {
        "action": "index",
        "document": {
            "id": "123",
            "title": "Doc",
            "body": "content",
        },
    }

    run._process_message(body, fake_os_client)

    assert calls == [("123", body["document"])]


def test_process_message_delete(monkeypatch: pytest.MonkeyPatch, fake_os_client: dict[str, Any]) -> None:
    calls: list[str] = []

    def fake_delete_document(client: Any, index: str, document_id: str) -> None:  # noqa: ANN401
        calls.append(document_id)

    monkeypatch.setattr(run, "delete_document", fake_delete_document)

    body = {
        "action": "delete",
        "document_id": "abc",
    }

    run._process_message(body, fake_os_client)

    assert calls == ["abc"]


def test_process_message_invalid_document(caplog: pytest.LogCaptureFixture, fake_os_client: dict[str, Any]) -> None:
    body = {
        "action": "index",
        "document": None,
    }

    run._process_message(body, fake_os_client)

    assert any("worker_invalid_document_payload" in record.message for record in caplog.records)


def test_process_message_unknown_action(caplog: pytest.LogCaptureFixture, fake_os_client: dict[str, Any]) -> None:
    run._process_message({"action": "noop"}, fake_os_client)

    assert any("worker_unknown_action" in record.message for record in caplog.records)
