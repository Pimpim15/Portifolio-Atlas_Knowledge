"""API de enfileiramento de tarefas."""

from .indexing import enqueue_document, enqueue_document_deletion

__all__ = ["enqueue_document", "enqueue_document_deletion"]
