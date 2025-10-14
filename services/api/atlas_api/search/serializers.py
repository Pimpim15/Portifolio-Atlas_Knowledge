"""Helpers to serialize documents for search index."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..db.models import Document


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.isoformat()


def serialize_document(document: Document) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "org_id": str(document.org_id),
        "title": document.title,
        "body": document.body,
        "tags": list(document.tags or []),
        "version": document.version,
        "created_at": _isoformat(document.created_at),
        "updated_at": _isoformat(document.updated_at or document.created_at),
    }
