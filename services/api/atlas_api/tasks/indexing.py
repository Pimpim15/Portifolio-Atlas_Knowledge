"""Compatibilidade retroativa para enfileirar eventos de documentos."""

from __future__ import annotations

from ..db.models import Document
from ..queue.publisher import enqueue_delete, enqueue_index


def enqueue_document(document: Document) -> None:
    enqueue_index(document)


def enqueue_document_deletion(document_id: str, org_id: str) -> None:
    enqueue_delete(document_id, org_id)
