"""Publish messages to the document events queue.

The helpers in this module send messages to SQS when the queue is
configured. For local development we degrade gracefully by applying the
indexing/deletion inline, ensuring that features such as reindexing and
full-text search remain functional even without Localstack or AWS
credentials.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import get_settings
from ..db.models import Document
from ..observability.logging import get_logger
from ..observability.metrics import REINDEX_DOCUMENT_ENQUEUED
from ..reindex.progress import mark_job_item_error, mark_job_item_started, mark_job_item_success
from ..search.mappings import DOC_INDEX
from ..search.os_client import delete_document, ensure_index_exists, get_client, index_document
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


def _send_message(payload: dict[str, Any]) -> bool:
    """Send the payload to SQS.

    Returns ``True`` when the message is successfully enqueued. ``False``
    indicates that the queue is not configured or that an error occurred.
    """

    settings = get_settings()
    if not settings.sqs_queue_url:
        logger.debug("sqs_queue_url_not_configured", payload_type=payload.get("action"))
        return False

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
        return False

    return True


def _ensure_index_ready() -> Any:
    client = get_client()
    ensure_index_exists(client, DOC_INDEX)
    return client


def _index_inline(document_payload: dict[str, Any]) -> None:
    client = _ensure_index_ready()
    index_document(client, DOC_INDEX, document_payload["id"], document_payload)


def _delete_inline(document_id: str) -> None:
    client = _ensure_index_ready()
    delete_document(client, DOC_INDEX, document_id)


def enqueue_index(document: Document) -> None:
    serialized = serialize_document(document)
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "index",
        "document": serialized,
    }
    if _send_message(payload):
        return

    logger.debug("inline_index_fallback", document_id=serialized.get("id"))
    try:
        _index_inline(serialized)
    except Exception as exc:  # pragma: no cover - local OpenSearch failure
        logger.exception("inline_index_failed", document_id=serialized.get("id"), error=str(exc))


def enqueue_reindex_document(job_id: str, document: Document, job_item_id: str | None = None) -> None:
    serialized = serialize_document(document)
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "index",
        "job_id": job_id,
        "document": serialized,
    }
    if job_item_id is not None:
        payload["job_item_id"] = job_item_id

    if _send_message(payload):
        REINDEX_DOCUMENT_ENQUEUED.inc()
        return

    logger.warning(
        "reindex_inline_fallback",
        job_id=job_id,
        job_item_id=job_item_id,
        reason="sqs_disabled_or_failed",
    )

    if job_item_id is not None:
        try:
            mark_job_item_started(job_id, job_item_id)
        except Exception:  # pragma: no cover - defensive log only
            logger.exception(
                "reindex_mark_started_failed",
                job_id=job_id,
                job_item_id=job_item_id,
            )

    try:
        _index_inline(serialized)
    except Exception as exc:  # pragma: no cover - inline indexing failure
        logger.exception(
            "reindex_inline_failed",
            job_id=job_id,
            job_item_id=job_item_id,
            error=str(exc),
        )
        if job_item_id is not None:
            try:
                mark_job_item_error(job_id, job_item_id, str(exc))
            except Exception:  # pragma: no cover
                logger.exception(
                    "reindex_mark_error_failed",
                    job_id=job_id,
                    job_item_id=job_item_id,
                    error=str(exc),
                )
        return

    if job_item_id is not None:
        try:
            mark_job_item_success(job_id, job_item_id)
        except Exception:  # pragma: no cover - defensive log
            logger.exception(
                "reindex_mark_success_failed",
                job_id=job_id,
                job_item_id=job_item_id,
            )

    REINDEX_DOCUMENT_ENQUEUED.inc()


def enqueue_delete(document_id: str, org_id: str) -> None:
    payload = {
        "source": DOCUMENT_EVENT_SOURCE,
        "action": "delete",
        "document_id": document_id,
        "org_id": org_id,
    }
    if _send_message(payload):
        return

    logger.debug("inline_delete_fallback", document_id=document_id)
    try:
        _delete_inline(document_id)
    except Exception as exc:  # pragma: no cover - local OpenSearch failure
        logger.exception("inline_delete_failed", document_id=document_id, error=str(exc))
