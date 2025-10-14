"""Busca full-text."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Document
from ..deps import CurrentUser, RBACGuard, get_db

router = APIRouter()


class SearchResponseItem(BaseModel):
    id: str
    title: str
    snippet: str
    tags: list[str]


class SearchResponse(BaseModel):
    results: list[SearchResponseItem]
    total: int


def _build_snippet(body: str, term: str) -> str:
    normalized_body = body.strip()
    if not normalized_body:
        return ""

    if not term:
        shortened = normalized_body[:200]
        return shortened + ("…" if len(normalized_body) > len(shortened) else "")

    lower_body = normalized_body.lower()
    lower_term = term.lower()
    idx = lower_body.find(lower_term)

    if idx == -1:
        shortened = normalized_body[:200]
        return shortened + ("…" if len(normalized_body) > len(shortened) else "")

    window = 160
    start = max(idx - window // 2, 0)
    end = min(idx + len(term) + window // 2, len(normalized_body))
    snippet = normalized_body[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(normalized_body) else ""
    return f"{prefix}{snippet}{suffix}"


@router.get("/", response_model=SearchResponse)
async def search(
    q: str = Query("", description="Termo de busca"),
    tags: str | None = Query(None, description="Lista de tags separadas por vírgula"),
    current_user: CurrentUser = Depends(RBACGuard(["viewer", "editor", "admin"])),
    session: AsyncSession = Depends(get_db),
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

    if q := q.strip():
        like_pattern = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Document.title).like(like_pattern),
                func.lower(Document.body).like(like_pattern),
            )
        )

    query_result = await session.execute(stmt)
    documents = list(query_result.scalars())

    filter_tags: list[str] = []
    if tags:
        filter_tags = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
        if filter_tags:
            documents = [
                doc
                for doc in documents
                if {tag.lower() for tag in (doc.tags or [])}.issuperset(filter_tags)
            ]

    results = [
        SearchResponseItem(
            id=str(doc.id),
            title=doc.title,
            snippet=_build_snippet(doc.body, q),
            tags=doc.tags or [],
        )
        for doc in documents
    ]

    return SearchResponse(results=results, total=len(results))
