from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from services.api.atlas_api.queue import publisher


@pytest.fixture(autouse=True)
def _configure_tracer() -> Iterator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


def test_send_message_includes_trace_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def send_message(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(publisher, "get_settings", lambda: SimpleNamespace(sqs_queue_url="https://queue"))
    monkeypatch.setattr(publisher, "get_sqs_client", lambda: FakeClient())
    monkeypatch.setattr(publisher, "ensure_queue_exists", lambda queue_url: "https://queue")

    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("parent"):
        result = publisher._send_message({"action": "index"})

    assert captured["QueueUrl"] == "https://queue"
    assert "MessageAttributes" in captured
    attrs = captured["MessageAttributes"]
    assert "traceparent" in attrs
    assert attrs["traceparent"]["DataType"] == "String"
    assert "StringValue" in attrs["traceparent"]
    assert result is True