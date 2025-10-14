"""Tasks Celery para indexação."""

from typing import Any

from celery import Celery

from ..config import get_settings
from ..search.mappings import DOC_INDEX
from ..search.os_client import delete_document, get_client, index_document

settings = get_settings()

celery_app = Celery("atlas-worker")
celery_app.conf.broker_url = str(settings.redis_url)
celery_app.conf.result_backend = str(settings.redis_url)


@celery_app.task(name="index_document")  # type: ignore[misc]
def index_document_task(document: dict[str, Any]) -> None:
    client = get_client()
    index_document(client, DOC_INDEX, document["id"], document)


@celery_app.task(name="delete_document")  # type: ignore[misc]
def delete_document_task(document_id: str) -> None:
    client = get_client()
    delete_document(client, DOC_INDEX, document_id)
