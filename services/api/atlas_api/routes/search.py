"""Busca full-text."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from opensearchpy import OpenSearchException
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Document
from ..deps import CurrentUser, RBACGuard, get_db
from ..search.mappings import DOC_INDEX
from ..search.os_client import ensure_index_exists, get_client
from ..observability.logging import get_logger

router = APIRouter()
logger = get_logger(component="api", module="search")


class SearchResponseItem(BaseModel):
    id: str
    title: str
    snippet: str
    tags: list[str]


class SearchResponse(BaseModel):
    results: list[SearchResponseItem]
    total: int


def _build_snippet(body: str, term: str) -> str:
    if not body:
        return ""

    normalized_body = " ".join(body.split())
    if not term:
        snippet = normalized_body[:200]
        return snippet + ("…" if len(normalized_body) > len(snippet) else "")

    lower_body = normalized_body.lower()
    lower_term = term.lower()
    idx = lower_body.find(lower_term)

    if idx == -1:
        snippet = normalized_body[:200]
        return snippet + ("…" if len(normalized_body) > len(snippet) else "")

    window = 160
    start = max(idx - window // 2, 0)
    end = min(idx + len(term) + window // 2, len(normalized_body))
    snippet = normalized_body[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(normalized_body) else ""
    return f"{prefix}{snippet}{suffix}"


async def _search_database(
    q: str,
    filter_tags: list[str],
    current_user: CurrentUser,
    session: AsyncSession,
) -> SearchResponse:
    stmt = (
        select(Document)
        .where(
            Document.org_id.in_(current_user.organization_ids),
            Document.deleted_at.is_(None),
        )
        .order_by(Document.updated_at.desc())
        .limit(100)
    )

    q_clean = q.strip()
    if q_clean:
        like_pattern = f"%{q_clean.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Document.title).like(like_pattern),
                func.lower(Document.body).like(like_pattern),
            )
        )

    query_result = await session.execute(stmt)
    documents = list(query_result.scalars())

    if filter_tags:
        required_tags = set(filter_tags)
        documents = [
            doc
            for doc in documents
            if required_tags.issubset({tag.lower() for tag in (doc.tags or [])})
        ]

    results = [
        SearchResponseItem(
            id=str(doc.id),
            title=doc.title,
            snippet=_build_snippet(doc.body or "", q_clean),
            tags=doc.tags or [],
        )
        for doc in documents
    ]

    return SearchResponse(results=results, total=len(results))


def _search_opensearch(q: str, filter_tags: list[str], current_user: CurrentUser) -> SearchResponse:
    client = get_client()
    ensure_index_exists(client, DOC_INDEX)

    filter_clause: list[dict[str, Any]] = [
        {"terms": {"org_id": [str(org_id) for org_id in current_user.organization_ids]}},
    ]

    for tag in filter_tags:
        filter_clause.append({"term": {"tags": tag}})

    must_clause: list[dict[str, Any]]
    if q:
        must_clause = [{"multi_match": {"query": q, "fields": ["title^3", "body"]}}]
    else:
        must_clause = [{"match_all": {}}]

    body = {
        "size": 100,
        "sort": [
            {"updated_at": {"order": "desc"}}
        ],
        "_source": ["id", "org_id", "title", "body", "tags", "updated_at"],
        "query": {
            "bool": {
                "must": must_clause,
                "filter": filter_clause,
            }
        },
        "highlight": {
            "fields": {
                "body": {
                    "type": "plain",
                    "fragment_size": 160,
                    "number_of_fragments": 1,
                }
            }
        },
    }

    response = client.search(index=DOC_INDEX, body=body)
    hits_meta = response.get("hits", {})
    total_meta = hits_meta.get("total", {})
    total = total_meta.get("value", len(hits_meta.get("hits", [])))

    results: list[SearchResponseItem] = []
    for hit in hits_meta.get("hits", []):
        source = hit.get("_source", {})
        highlight = hit.get("highlight", {}).get("body")
        snippet = "...".join(highlight) if highlight else _build_snippet(source.get("body", ""), q)
        results.append(
            SearchResponseItem(
                id=str(source.get("id")),
                title=source.get("title", ""),
                snippet=snippet,
                tags=list(source.get("tags", [])),
            )
        )

    return SearchResponse(results=results, total=total)


@router.get("", response_model=SearchResponse)
@router.get("/", response_model=SearchResponse, include_in_schema=False)
async def search(
    q: str = Query("", description="Termo de busca"),
    tags: str | None = Query(None, description="Lista de tags separadas por vírgula"),
    current_user: CurrentUser = Depends(RBACGuard(["viewer", "editor", "admin"])),
    session: AsyncSession = Depends(get_db),
) -> SearchResponse:
    filter_tags = [tag.strip().lower() for tag in (tags or "").split(",") if tag.strip()]

    try:
        return _search_opensearch(q.strip(), filter_tags, current_user)
    except OpenSearchException:
        logger.exception(
            "search_opensearch_failed",
            extra={"query": q, "tags": filter_tags},
        )
    except Exception:  # pragma: no cover - fallback safety
        logger.exception(
            "search_opensearch_unexpected_error",
            extra={"query": q, "tags": filter_tags},
        )

    return await _search_database(q, filter_tags, current_user, session)
