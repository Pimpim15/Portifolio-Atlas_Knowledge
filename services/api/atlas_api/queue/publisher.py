"""Publish messages to the document events queue."""

from __future__ import annotations

import json
from typing import Any

from ..config import get_settings
from ..db.models import Document
from ..observability.logging import get_logger
from ..observability.metrics import REINDEX_DOCUMENT_ENQUEUED
from ..search.serializers import serialize_document
from .sqs import ensure_queue_exists, get_sqs_client

logger = get_logger(component="api", module="queue.publisher")

DOCUMENT_EVENT_SOURCE = "atlas.documents"


def _build_trace_message_attributes() -> dict[str, dict[str, str]]:
    try:
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    except ImportError:  # pragma: no cover - optional instrumentation
        return {}

    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    attributes: dict[str, dict[str, str]] = {}
    for key, value in carrier.items():
        if not value:
            continue
        attributes[key] = {"DataType": "String", "StringValue": value}
    return attributes


def _send_message(payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.sqs_queue_url:
        logger.debug("sqs_queue_url_not_configured", payload_type=payload.get("action"))
        return

    client = get_sqs_client()
    ensure_queue_exists(settings.sqs_queue_url)
    message_attributes = _build_trace_message_attributes()
    try:
        params: dict[str, Any] = {
            "QueueUrl": settings.sqs_queue_url,
            "MessageBody": json.dumps(payload),
        }
        if message_attributes:
            params["MessageAttributes"] = message_attributes
        client.send_message(**params)
    except Exception as exc:  # pragma: no cover - IO failure
        logger.exception("sqs_send_failed", action=payload.get("action"), error=str(exc))


def enqueue_index(document: Document) -> None:
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "index",
        "document": serialize_document(document),
    }
    _send_message(payload)


def enqueue_reindex_document(job_id: str, document: Document, job_item_id: str | None = None) -> None:
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "index",
        "job_id": job_id,
        "document": serialize_document(document),
    }
    if job_item_id is not None:
        payload["job_item_id"] = job_item_id
    _send_message(payload)
    REINDEX_DOCUMENT_ENQUEUED.inc()


def enqueue_delete(document_id: str, org_id: str) -> None:
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "delete",
        "document_id": document_id,
        "org_id": org_id,
    }
    _send_message(payload)
