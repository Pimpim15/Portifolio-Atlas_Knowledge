"""Worker responsável por consumir eventos do SQS e indexar documentos."""

from __future__ import annotations

import contextlib
import json
import time
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
    WORKER_PROCESSING_ERRORS,
    WORKER_PROCESSING_LATENCY,
)
from services.api.atlas_api.observability.tracing import setup_tracing
from services.api.atlas_api.queue.sqs import ensure_queue_exists, get_sqs_client
from services.api.atlas_api.search.mappings import DOC_INDEX
from services.api.atlas_api.search.os_client import (
    delete_document,
    ensure_index_exists,
    get_client,
    index_document,
)

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    trace = None

logger = get_logger(component="worker")
TRACER = trace.get_tracer("atlas-worker") if trace else None


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

    with span_cm:
        if action == "index":
            if document is None:
                logger.warning(
                    "worker_invalid_document_payload",
                    payload=body,
                )
            elif not document_id:
                logger.warning(
                    "worker_missing_document_id",
                    payload=document,
                )
            else:
                index_document(client, DOC_INDEX, document_id, document)
                WORKER_ACTION_COUNT.labels(action="index").inc()
                success = True
        elif action == "delete":
            if not document_id:
                logger.warning(
                    "worker_missing_document_id_delete",
                    payload=body,
                )
            else:
                delete_document(client, DOC_INDEX, str(document_id))
                WORKER_ACTION_COUNT.labels(action="delete").inc()
                success = True
        else:
            logger.warning(
                "worker_unknown_action",
                action=action,
            )
            WORKER_ACTION_COUNT.labels(action=action_label).inc()

    elapsed = time.perf_counter() - start
    WORKER_PROCESSING_LATENCY.labels(action_label).observe(elapsed)
    if not success:
        WORKER_PROCESSING_ERRORS.labels(action_label).inc()


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

            try:
                bind_context(
                    message_id=message.get("MessageId"),
                    receipt_handle=receipt_handle,
                    queue_url=settings.sqs_queue_url,
                )
                _process_message(payload, os_client)
            except Exception:  # pragma: no cover - processing failure
                logger.exception(
                    "worker_processing_failed",
                    payload=payload,
                )
            finally:
                unbind_context("message_id", "receipt_handle", "queue_url")
                try:
                    client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=receipt_handle)
                except (BotoCoreError, ClientError):  # pragma: no cover
                    logger.exception(
                        "sqs_delete_failed",
                        payload=payload,
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
