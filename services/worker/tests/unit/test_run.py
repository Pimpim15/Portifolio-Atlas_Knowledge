"""Unit tests for the worker poller logic."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

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


def test_handle_message_observes_age_and_reuses_trace(
    monkeypatch: pytest.MonkeyPatch, fake_os_client: dict[str, Any]
) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    run.TRACER = trace.get_tracer("atlas-worker-test")

    observed: list[float] = []
    monkeypatch.setattr(
        run,
        "WORKER_MESSAGE_AGE_SECONDS",
        SimpleNamespace(observe=lambda value: observed.append(value)),
    )

    contexts: list[Any] = []

    def fake_process_message(body: dict[str, Any], client: Any) -> None:  # noqa: ANN401
        span = trace.get_current_span()
        contexts.append(span.get_span_context())

    monkeypatch.setattr(run, "_process_message", fake_process_message)

    class FakeClient:
        def __init__(self) -> None:
            self.deleted = False

        def delete_message(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.deleted = True

    client = FakeClient()

    tracer = trace.get_tracer("producer")
    carrier: dict[str, str] = {}
    with tracer.start_as_current_span("producer-span") as span:
        TraceContextTextMapPropagator().inject(carrier)
        producer_context = span.get_span_context()

    sent_timestamp_ms = int((time.time() - 1) * 1000)
    message = {
        "MessageId": "1",
        "ReceiptHandle": "abc",
        "MessageAttributes": {
            key: {"StringValue": value, "DataType": "String"} for key, value in carrier.items()
        },
        "Attributes": {"SentTimestamp": str(sent_timestamp_ms)},
    }
    payload = {"action": "index", "document": {"id": "1"}}

    run._handle_message(
        client=client,
        queue_url="https://queue",
        os_client=fake_os_client,
        message=message,
        payload=payload,
        receipt_handle="abc",
    )

    assert client.deleted is True
    assert observed and pytest.approx(observed[0], rel=0.2, abs=0.5) == 1
    assert contexts and contexts[0].trace_id == producer_context.trace_id
