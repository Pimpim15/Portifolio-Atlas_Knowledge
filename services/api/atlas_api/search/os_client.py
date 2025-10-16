"""Cliente OpenSearch com retry básico."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from opensearchpy import OpenSearch, RequestsHttpConnection

from ..config import get_settings
from .mappings import DOC_MAPPING


class _MockIndices:
    def exists(self, *, index: str) -> bool:  # noqa: D401 - comportamento trivial
        return True

    def create(self, *, index: str, body: dict[str, Any]) -> None:  # noqa: D401 - comportamento trivial
        return None


class _MockOpenSearch:
    is_mock = True

    def __init__(self) -> None:
        self.indices = _MockIndices()

    def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:  # noqa: D401
        return {"hits": {"total": {"value": 0}, "hits": []}}

    def index(self, *, index: str, id: str, body: dict[str, Any]) -> None:  # noqa: D401 - comportamento trivial
        return None

    def delete(self, *, index: str, id: str, ignore: list[int]) -> None:  # noqa: D401 - comportamento trivial
        return None


def _should_use_mock() -> bool:
    flag = os.environ.get("OPENSEARCH_STUB", "").lower()
    if flag in {"1", "true", "yes"}:
        return True
    endpoint = get_settings().opensearch_endpoint
    return endpoint.startswith("stub://")


def get_client() -> Any:
    if _should_use_mock():
        return _MockOpenSearch()
    settings = get_settings()
    endpoint = urlparse(settings.opensearch_endpoint)
    if endpoint.hostname is None:
        raise ValueError("OPENSEARCH_ENDPOINT inválido: hostname ausente")

    default_port = 443 if endpoint.scheme == "https" else 9200

    return OpenSearch(
        hosts=[{"host": endpoint.hostname, "port": endpoint.port or default_port}],
        http_auth=None,
        use_ssl=endpoint.scheme == "https",
        verify_certs=endpoint.scheme == "https",
        connection_class=RequestsHttpConnection,
    )


def index_document(client: OpenSearch, index: str, document_id: str, payload: dict[str, Any]) -> None:
    if getattr(client, "is_mock", False):  # pragma: no cover - caminho local de benchmark
        return
    client.index(index=index, id=document_id, body=payload)


def delete_document(client: OpenSearch, index: str, document_id: str) -> None:
    if getattr(client, "is_mock", False):  # pragma: no cover - caminho local de benchmark
        return
    client.delete(index=index, id=document_id, ignore=[404])


def ensure_index_exists(client: OpenSearch, index: str) -> None:
    if getattr(client, "is_mock", False):  # pragma: no cover - caminho local de benchmark
        return
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body=DOC_MAPPING)
