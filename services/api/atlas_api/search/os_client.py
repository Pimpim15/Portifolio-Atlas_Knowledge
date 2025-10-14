"""Cliente OpenSearch com retry básico."""

from typing import Any
from urllib.parse import urlparse

from opensearchpy import OpenSearch, RequestsHttpConnection

from ..config import get_settings


def get_client() -> OpenSearch:
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
    client.index(index=index, id=document_id, body=payload)
