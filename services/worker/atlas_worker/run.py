"""Worker responsável por consumir eventos do SQS e indexar documentos."""

from __future__ import annotations

import json
import time
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from services.api.atlas_api.config import get_settings
from services.api.atlas_api.observability.logging import configure_logging, get_logger
from services.api.atlas_api.queue.sqs import ensure_queue_exists, get_sqs_client
from services.api.atlas_api.search.mappings import DOC_INDEX
from services.api.atlas_api.search.os_client import (
    delete_document,
    ensure_index_exists,
    get_client,
    index_document,
)

logger = get_logger(component="worker")


def _process_message(body: dict[str, Any], client: Any) -> None:

    action = body.get("action")
    if action == "index":
        document = body.get("document")
        if not isinstance(document, dict):
            logger.warning(
                "worker_invalid_document_payload",
                payload=body,
            )
            return
        document_id = document.get("id")
        if not document_id:
            logger.warning(
                "worker_missing_document_id",
                payload=document,
            )
            return
        index_document(client, DOC_INDEX, document_id, document)
    elif action == "delete":
        document_id = body.get("document_id")
        if not document_id:
            logger.warning(
                "worker_missing_document_id_delete",
                payload=body,
            )
            return
        delete_document(client, DOC_INDEX, document_id)
    else:
        logger.warning(
            "worker_unknown_action",
            action=action,
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
                _process_message(payload, os_client)
            except Exception:  # pragma: no cover - processing failure
                logger.exception(
                    "worker_processing_failed",
                    payload=payload,
                )
            finally:
                try:
                    client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=receipt_handle)
                except (BotoCoreError, ClientError):  # pragma: no cover
                    logger.exception(
                        "sqs_delete_failed",
                        payload=payload,
                    )


def main() -> None:
    configure_logging()
    logger.info("worker_started")
    while True:
        _poll_loop()
        time.sleep(5)


if __name__ == "__main__":
    main()
