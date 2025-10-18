"""Unit tests for the worker poller logic."""

from __future__ import annotations

import json
import time
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from botocore.exceptions import ClientError
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from services.api.atlas_api.config import Settings
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

    outcome = run._process_message(body, fake_os_client, attempt=1, max_attempts=5)

    assert calls == [("123", body["document"])]
    assert outcome.success is True
    assert outcome.action == "index"


def test_process_message_delete(monkeypatch: pytest.MonkeyPatch, fake_os_client: dict[str, Any]) -> None:
    calls: list[str] = []

    def fake_delete_document(client: Any, index: str, document_id: str) -> None:  # noqa: ANN401
        calls.append(document_id)

    monkeypatch.setattr(run, "delete_document", fake_delete_document)

    body = {
        "action": "delete",
        "document_id": "abc",
    }

    outcome = run._process_message(body, fake_os_client, attempt=1, max_attempts=5)

    assert calls == ["abc"]
    assert outcome.success is True
    assert outcome.action == "delete"


def test_process_message_invalid_document(caplog: pytest.LogCaptureFixture, fake_os_client: dict[str, Any]) -> None:
    body = {
        "action": "index",
        "document": None,
    }

    outcome = run._process_message(body, fake_os_client, attempt=1, max_attempts=5)

    assert outcome.success is False
    assert outcome.error_message == "invalid_document_payload"
    assert any("worker_invalid_document_payload" in record.message for record in caplog.records)


def test_process_message_unknown_action(caplog: pytest.LogCaptureFixture, fake_os_client: dict[str, Any]) -> None:
    outcome = run._process_message({"action": "noop"}, fake_os_client, attempt=1, max_attempts=5)

    assert outcome.success is False
    assert outcome.error_message == "unknown_action"
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

    def fake_process_message(
        body: dict[str, Any],
        client: Any,
        *,
        attempt: int,
        max_attempts: int,
    ) -> run.ProcessingOutcome:  # noqa: ANN401
        span = trace.get_current_span()
        contexts.append(span.get_span_context())
        assert attempt == 1
        assert max_attempts == 3
        return run.ProcessingOutcome(
            success=True,
            action=str(body.get("action") or "unknown"),
            job_id=None,
            job_item_id=None,
        )

    monkeypatch.setattr(run, "_process_message", fake_process_message)

    class FakeClient:
        def __init__(self) -> None:
            self.deleted = False

        def delete_message(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.deleted = True

    client = FakeClient()
    settings = Settings(
        WORKER_MAX_ATTEMPTS=3,
        WORKER_RETRY_BACKOFF_SECONDS=10,
        WORKER_RETRY_BACKOFF_MAX_SECONDS=60,
    )

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
        "Attributes": {
            "SentTimestamp": str(sent_timestamp_ms),
            "ApproximateReceiveCount": "1",
        },
    }
    payload = {"action": "index", "document": {"id": "1"}}

    run._handle_message(
        settings=settings,
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


def test_handle_message_retries_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    job_item_id = uuid.uuid4()

    def fake_process_message(
        body: dict[str, Any],
        client: Any,
        *,
        attempt: int,
        max_attempts: int,
    ) -> run.ProcessingOutcome:  # noqa: ANN401
        assert attempt == 2
        assert max_attempts == 5
        return run.ProcessingOutcome(
            success=False,
            action="index",
            job_id=job_id,
            job_item_id=job_item_id,
            error_message="boom",
        )

    monkeypatch.setattr(run, "_process_message", fake_process_message)

    class CounterStub:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def labels(self, action: str) -> SimpleNamespace:
            self.calls.append(action)
            return SimpleNamespace(inc=lambda: self.calls.append(f"{action}_inc"))

    retry_counter = CounterStub()
    monkeypatch.setattr(run, "WORKER_RETRY_COUNT", retry_counter)

    retry_marks: list[tuple[uuid.UUID, uuid.UUID, str]] = []
    monkeypatch.setattr(
        run,
        "mark_job_item_retry",
        lambda job, item, reason: retry_marks.append((job, item, reason)),
    )

    class FakeClient:
        def __init__(self) -> None:
            self.sent: list[dict[str, Any]] = []
            self.deleted: list[dict[str, Any]] = []
            self.visibility: list[dict[str, Any]] = []

        def send_message(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.sent.append(kwargs)

        def delete_message(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.deleted.append(kwargs)

        def change_message_visibility(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.visibility.append(kwargs)

    client = FakeClient()
    settings = Settings(
        WORKER_MAX_ATTEMPTS=5,
        WORKER_RETRY_BACKOFF_SECONDS=30,
        WORKER_RETRY_BACKOFF_MAX_SECONDS=120,
    )
    sent_timestamp_ms = int(time.time() * 1000)
    message = {
        "MessageId": "retry",
        "ReceiptHandle": "handle",
        "MessageAttributes": {},
        "Attributes": {
            "SentTimestamp": str(sent_timestamp_ms),
            "ApproximateReceiveCount": "2",
        },
    }
    payload = {
        "action": "index",
        "document": {"id": "doc"},
        "job_id": str(job_id),
        "job_item_id": str(job_item_id),
    }

    run._handle_message(
        settings=settings,
        client=client,
        queue_url="https://queue",
        os_client={},
        message=message,
        payload=payload,
        receipt_handle="handle",
    )

    assert client.sent and client.sent[0]["DelaySeconds"] == 60
    assert client.sent[0]["MessageBody"] == json.dumps(payload)
    assert client.deleted and client.deleted[0]["ReceiptHandle"] == "handle"
    assert not client.visibility
    assert retry_counter.calls == ["index", "index_inc"]
    assert retry_marks == [(job_id, job_item_id, "boom")]


def test_handle_message_retries_with_visibility_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    job_item_id = uuid.uuid4()

    def fake_process_message(
        body: dict[str, Any],
        client: Any,
        *,
        attempt: int,
        max_attempts: int,
    ) -> run.ProcessingOutcome:  # noqa: ANN401
        assert attempt == 2
        assert max_attempts == 5
        return run.ProcessingOutcome(
            success=False,
            action="index",
            job_id=job_id,
            job_item_id=job_item_id,
            error_message="boom",
        )

    monkeypatch.setattr(run, "_process_message", fake_process_message)

    class CounterStub:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def labels(self, action: str) -> SimpleNamespace:
            self.calls.append(action)
            return SimpleNamespace(inc=lambda: self.calls.append(f"{action}_inc"))

    retry_counter = CounterStub()
    monkeypatch.setattr(run, "WORKER_RETRY_COUNT", retry_counter)

    retry_marks: list[tuple[uuid.UUID, uuid.UUID, str]] = []
    monkeypatch.setattr(
        run,
        "mark_job_item_retry",
        lambda job, item, reason: retry_marks.append((job, item, reason)),
    )

    class FakeClient:
        def __init__(self) -> None:
            self.sent: list[dict[str, Any]] = []
            self.deleted: list[dict[str, Any]] = []
            self.visibility: list[dict[str, Any]] = []

        def send_message(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.sent.append(kwargs)
            raise ClientError({"Error": {"Code": "Throttling", "Message": "rate"}}, "SendMessage")

        def delete_message(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.deleted.append(kwargs)

        def change_message_visibility(self, **kwargs: Any) -> None:  # noqa: ANN401
            self.visibility.append(kwargs)

    client = FakeClient()
    settings = Settings(
        WORKER_MAX_ATTEMPTS=5,
        WORKER_RETRY_BACKOFF_SECONDS=30,
        WORKER_RETRY_BACKOFF_MAX_SECONDS=120,
    )
    sent_timestamp_ms = int(time.time() * 1000)
    message = {
        "MessageId": "retry",
        "ReceiptHandle": "handle",
        "MessageAttributes": {},
        "Attributes": {
            "SentTimestamp": str(sent_timestamp_ms),
            "ApproximateReceiveCount": "2",
        },
    }
    payload = {
        "action": "index",
        "document": {"id": "doc"},
        "job_id": str(job_id),
        "job_item_id": str(job_item_id),
    }

    run._handle_message(
        settings=settings,
        client=client,
        queue_url="https://queue",
        os_client={},
        message=message,
        payload=payload,
        receipt_handle="handle",
    )

    assert client.sent and client.sent[0]["DelaySeconds"] == 60
    assert not client.deleted
    assert client.visibility and client.visibility[0]["VisibilityTimeout"] == 60
    assert retry_counter.calls == ["index", "index_inc"]
    assert retry_marks == [(job_id, job_item_id, "boom")]


def test_handle_message_marks_error_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    job_item_id = uuid.uuid4()

    def fake_process_message(
        body: dict[str, Any],
        client: Any,
        *,
        attempt: int,
        max_attempts: int,
    ) -> run.ProcessingOutcome:  # noqa: ANN401
        assert attempt == 3
        assert max_attempts == 3
        return run.ProcessingOutcome(
            success=False,
            action="index",
            job_id=job_id,
            job_item_id=job_item_id,
            error_message="boom",
        )

    monkeypatch.setattr(run, "_process_message", fake_process_message)

    error_marks: list[tuple[uuid.UUID, uuid.UUID, str]] = []
    monkeypatch.setattr(
        run,
        "mark_job_item_error",
        lambda job, item, reason: error_marks.append((job, item, reason)),
    )
    def fail_retry(*_args: Any, **_kwargs: Any) -> None:  # noqa: ANN401
        raise AssertionError("retry should not be called")

    monkeypatch.setattr(run, "mark_job_item_retry", fail_retry)

    class CounterStub:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def labels(self, action: str) -> SimpleNamespace:
            self.calls.append(action)
            return SimpleNamespace(inc=lambda: self.calls.append(f"{action}_inc"))

    retry_counter = CounterStub()
    monkeypatch.setattr(run, "WORKER_RETRY_COUNT", retry_counter)

    class FakeClient:
        def __init__(self) -> None:
            self.deleted = False
            self.visibility_called = False

        def send_message(self, **kwargs: Any) -> None:  # noqa: ANN401
            raise AssertionError("send_message should not be called when attempts exhausted")

        def delete_message(self, **_kwargs: Any) -> None:  # noqa: ANN401
            self.deleted = True

        def change_message_visibility(self, **_kwargs: Any) -> None:  # noqa: ANN401
            self.visibility_called = True

    client = FakeClient()
    settings = Settings(
        WORKER_MAX_ATTEMPTS=3,
        WORKER_RETRY_BACKOFF_SECONDS=30,
        WORKER_RETRY_BACKOFF_MAX_SECONDS=120,
    )
    sent_timestamp_ms = int(time.time() * 1000)
    message = {
        "MessageId": "fail",
        "ReceiptHandle": "handle",
        "MessageAttributes": {},
        "Attributes": {
            "SentTimestamp": str(sent_timestamp_ms),
            "ApproximateReceiveCount": "3",
        },
    }
    payload = {
        "action": "index",
        "document": {"id": "doc"},
        "job_id": str(job_id),
        "job_item_id": str(job_item_id),
    }

    run._handle_message(
        settings=settings,
        client=client,
        queue_url="https://queue",
        os_client={},
        message=message,
        payload=payload,
        receipt_handle="handle",
    )

    assert client.deleted is True
    assert client.visibility_called is False
    assert error_marks == [(job_id, job_item_id, "boom")]
    assert retry_counter.calls == []


def test_main_starts_metrics_server(monkeypatch: pytest.MonkeyPatch) -> None:
    start_calls: list[int] = []
    tracing_calls: list[str] = []

    monkeypatch.setattr(run, "configure_logging", lambda: tracing_calls.append("logging"))
    monkeypatch.setattr(run, "setup_tracing", lambda name: tracing_calls.append(name))
    monkeypatch.setattr(run, "start_http_server", lambda port: start_calls.append(port))

    def stop_loop() -> None:
        raise StopIteration

    monkeypatch.setattr(run, "_poll_loop", stop_loop)
    monkeypatch.setattr(run, "get_settings", lambda: SimpleNamespace(worker_metrics_port=9101))

    with pytest.raises(StopIteration):
        run.main()

    assert start_calls == [9101]
    assert "logging" in tracing_calls
    assert "atlas-worker" in tracing_calls
