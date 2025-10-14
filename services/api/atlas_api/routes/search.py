"""Busca full-text."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import RBACGuard

router = APIRouter()


class SearchResponseItem(BaseModel):
    id: str
    title: str
    snippet: str
    tags: list[str]


class SearchResponse(BaseModel):
    results: list[SearchResponseItem]
    total: int


@router.get("/", response_model=SearchResponse, dependencies=[Depends(RBACGuard(["viewer", "editor", "admin"]))])
def search(q: str, tags: str | None = None) -> SearchResponse:
    return SearchResponse(results=[], total=0)
