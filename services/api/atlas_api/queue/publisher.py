"""Publish messages to the document events queue."""

from __future__ import annotations

import json
from typing import Any

from ..config import get_settings
from ..db.models import Document
from ..observability.logging import get_logger
from ..search.serializers import serialize_document
from .sqs import ensure_queue_exists, get_sqs_client

logger = get_logger(component="api", module="queue.publisher")

DOCUMENT_EVENT_SOURCE = "atlas.documents"


def _send_message(payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.sqs_queue_url:
        logger.debug("sqs_queue_url_not_configured", payload_type=payload.get("action"))
        return

    client = get_sqs_client()
    ensure_queue_exists(settings.sqs_queue_url)
    try:
        client.send_message(QueueUrl=settings.sqs_queue_url, MessageBody=json.dumps(payload))
    except Exception as exc:  # pragma: no cover - IO failure
        logger.exception("sqs_send_failed", action=payload.get("action"), error=str(exc))


def enqueue_index(document: Document) -> None:
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "index",
        "document": serialize_document(document),
    }
    _send_message(payload)


def enqueue_delete(document_id: str, org_id: str) -> None:
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "delete",
        "document_id": document_id,
        "org_id": org_id,
    }
    _send_message(payload)
