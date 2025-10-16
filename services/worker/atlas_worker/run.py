"""Worker responsável por consumir eventos do SQS e indexar documentos."""

from __future__ import annotations

import contextlib
import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import]

from services.api.atlas_api.config import get_settings
from services.api.atlas_api.observability.logging import (
    bind_context,
    configure_logging,
    get_logger,
    unbind_context,
)
from services.api.atlas_api.observability.metrics import (
    WORKER_ACTION_COUNT,
    WORKER_MESSAGE_AGE_SECONDS,
    WORKER_PROCESSING_ERRORS,
    WORKER_PROCESSING_LATENCY,
)
from services.api.atlas_api.observability.tracing import setup_tracing
from services.api.atlas_api.queue.sqs import ensure_queue_exists, get_sqs_client
from services.api.atlas_api.reindex.progress import (
    mark_job_item_error,
    mark_job_item_started,
    mark_job_item_success,
)
from services.api.atlas_api.search.mappings import DOC_INDEX
from services.api.atlas_api.search.os_client import (
    delete_document,
    ensure_index_exists,
    get_client,
    index_document,
)

try:  # pragma: no cover - optional dependency
    from opentelemetry import context as otel_context  # type: ignore[import]
    from opentelemetry import trace  # type: ignore[import]
    from opentelemetry.trace.propagation.tracecontext import (  # type: ignore[import]
        TraceContextTextMapPropagator,
    )
except ImportError:  # pragma: no cover - optional dependency
    trace = None
    otel_context = None
    TraceContextTextMapPropagator = None

logger = get_logger(component="worker")
TRACER = trace.get_tracer("atlas-worker") if trace else None


@contextlib.contextmanager
def _attach_trace_from_message_attributes(message_attributes: dict[str, Any]) -> Iterator[None]:
    if TraceContextTextMapPropagator is None or otel_context is None:
        yield
        return

    carrier: dict[str, str] = {}
    for key, attr in message_attributes.items():
        if not isinstance(attr, dict):
            continue
        value = attr.get("StringValue")
        if isinstance(value, str) and value:
            carrier[key] = value

    if not carrier:
        yield
        return

    context = TraceContextTextMapPropagator().extract(carrier)
    token = otel_context.attach(context)
    try:
        yield
    finally:
        otel_context.detach(token)


def _observe_message_age(attributes: dict[str, Any]) -> None:
    sent_ts = attributes.get("SentTimestamp")
    if sent_ts is None:
        return

    try:
        sent_epoch_ms = int(sent_ts)
    except (TypeError, ValueError):
        logger.debug("worker_invalid_sent_timestamp", sent_timestamp=sent_ts)
        return

    age_seconds = max(0.0, time.time() - (sent_epoch_ms / 1000.0))
    WORKER_MESSAGE_AGE_SECONDS.observe(age_seconds)


def _process_message(body: dict[str, Any], client: Any) -> None:
    action = body.get("action")
    action_label = str(action or "unknown")
    document = body.get("document") if isinstance(body.get("document"), dict) else None
    document_id = None
    if document:
        document_id = document.get("id")
    elif body.get("document_id"):
        document_id = body["document_id"]

    span_cm = (
        TRACER.start_as_current_span(
            "worker.process_message",
            attributes={
                "atlas.worker.action": action_label,
                "atlas.worker.job_id": body.get("job_id"),
                "atlas.worker.job_item_id": body.get("job_item_id"),
                "atlas.worker.document_id": document_id,
            },
        )
        if TRACER
        else contextlib.nullcontext()
    )

    start = time.perf_counter()
    success = False
    error_message: str | None = None

    job_uuid: uuid.UUID | None = None
    job_item_uuid: uuid.UUID | None = None

    job_id_raw = body.get("job_id")
    job_item_id_raw = body.get("job_item_id")

    if isinstance(job_id_raw, uuid.UUID):
        job_uuid = job_id_raw
    elif isinstance(job_id_raw, str):
        try:
            job_uuid = uuid.UUID(job_id_raw)
        except ValueError:
            logger.warning("worker_invalid_job_id", job_id=job_id_raw)

    if isinstance(job_item_id_raw, uuid.UUID):
        job_item_uuid = job_item_id_raw
    elif isinstance(job_item_id_raw, str):
        try:
            job_item_uuid = uuid.UUID(job_item_id_raw)
        except ValueError:
            logger.warning("worker_invalid_job_item_id", job_item_id=job_item_id_raw)

    job_context = job_uuid is not None and job_item_uuid is not None

    with span_cm:
        if job_context:
            try:
                mark_job_item_started(job_uuid, job_item_uuid)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception(
                    "worker_mark_job_item_started_failed",
                    job_id=str(job_uuid),
                    job_item_id=str(job_item_uuid),
                )

        if action == "index":
            if document is None:
                logger.warning(
                    "worker_invalid_document_payload",
                    payload=body,
                )
                error_message = "invalid_document_payload"
            elif not document_id:
                logger.warning(
                    "worker_missing_document_id",
                    payload=document,
                )
                error_message = "missing_document_id"
            else:
                try:
                    index_document(client, DOC_INDEX, document_id, document)
                except Exception as exc:  # pragma: no cover - external client failure
                    error_message = str(exc)
                    logger.exception(
                        "worker_index_document_failed",
                        document_id=document_id,
                        job_id=str(job_uuid) if job_uuid else None,
                        job_item_id=str(job_item_uuid) if job_item_uuid else None,
                    )
                else:
                    WORKER_ACTION_COUNT.labels(action="index").inc()
                    success = True
        elif action == "delete":
            if not document_id:
                logger.warning(
                    "worker_missing_document_id_delete",
                    payload=body,
                )
                error_message = "missing_document_id"
            else:
                try:
                    delete_document(client, DOC_INDEX, str(document_id))
                except Exception as exc:  # pragma: no cover - external client failure
                    error_message = str(exc)
                    logger.exception(
                        "worker_delete_document_failed",
                        document_id=document_id,
                    )
                else:
                    WORKER_ACTION_COUNT.labels(action="delete").inc()
                    success = True
        else:
            logger.warning(
                "worker_unknown_action",
                action=action,
            )
            WORKER_ACTION_COUNT.labels(action=action_label).inc()
            error_message = "unknown_action"

    elapsed = time.perf_counter() - start
    WORKER_PROCESSING_LATENCY.labels(action_label).observe(elapsed)
    if not success:
        WORKER_PROCESSING_ERRORS.labels(action_label).inc()

    if job_context:
        if success:
            try:
                mark_job_item_success(job_uuid, job_item_uuid)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception(
                    "worker_mark_job_item_success_failed",
                    job_id=str(job_uuid),
                    job_item_id=str(job_item_uuid),
                )
        else:
            failure_reason = error_message or "worker_processing_failed"
            try:
                mark_job_item_error(job_uuid, job_item_uuid, failure_reason)
            except Exception:  # pragma: no cover - defensive logging
                logger.exception(
                    "worker_mark_job_item_error_failed",
                    job_id=str(job_uuid),
                    job_item_id=str(job_item_uuid),
                    failure_reason=failure_reason,
                )


def _handle_message(
    *,
    client: Any,
    queue_url: str,
    os_client: Any,
    message: dict[str, Any],
    payload: dict[str, Any],
    receipt_handle: str,
) -> None:
    try:
        _observe_message_age(message.get("Attributes", {}))

        with _attach_trace_from_message_attributes(message.get("MessageAttributes", {})):
            bind_context(
                message_id=message.get("MessageId"),
                receipt_handle=receipt_handle,
                queue_url=queue_url,
            )
            try:
                _process_message(payload, os_client)
            finally:
                unbind_context("message_id", "receipt_handle", "queue_url")
    except Exception:  # pragma: no cover - processing failure
        logger.exception(
            "worker_processing_failed",
            payload=payload,
        )
    finally:
        try:
            client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
        except (BotoCoreError, ClientError):  # pragma: no cover
            logger.exception(
                "sqs_delete_failed",
                payload=payload,
            )


def _poll_loop() -> None:
    settings = get_settings()
    if not settings.sqs_queue_url:
        logger.error("sqs_queue_url_not_configured")
        time.sleep(5)
        return

    client = get_sqs_client()
    ensure_queue_exists(settings.sqs_queue_url)
    os_client = get_client()
    ensure_index_exists(os_client, DOC_INDEX)

    while True:
        try:
            response = client.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
                VisibilityTimeout=60,
                MessageAttributeNames=["All"],
                AttributeNames=["SentTimestamp"],
            )
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - runtime failure
            logger.exception(
                "sqs_receive_failed",
                error=str(exc),
            )
            time.sleep(5)
            continue

        messages = response.get("Messages", [])
        if not messages:
            continue

        for message in messages:
            receipt_handle = message.get("ReceiptHandle")
            body_raw = message.get("Body")
            if not receipt_handle or not body_raw:
                logger.warning(
                    "worker_missing_body_or_receipt",
                    message=message,
                )
                continue

            try:
                payload = json.loads(body_raw)
            except json.JSONDecodeError:
                logger.warning(
                    "worker_invalid_json",
                    body=body_raw,
                )
                client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=receipt_handle)
                continue

            _handle_message(
                client=client,
                queue_url=settings.sqs_queue_url,
                os_client=os_client,
                message=message,
                payload=payload,
                receipt_handle=receipt_handle,
            )


def main() -> None:
    configure_logging()
    setup_tracing("atlas-worker")
    logger.info("worker_started")
    while True:
        _poll_loop()
        time.sleep(5)


if __name__ == "__main__":
    main()
