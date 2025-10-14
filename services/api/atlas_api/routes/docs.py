"""CRUD de documentos."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import RBACGuard

router = APIRouter()


class DocumentBase(BaseModel):
    title: str
    body: str
    tags: list[str] = []


class DocumentOut(DocumentBase):
    id: str
    version: int


_DOCUMENTS: dict[str, DocumentOut] = {}


@router.post("/", response_model=DocumentOut, dependencies=[Depends(RBACGuard(["editor", "admin"]))])
def create_document(payload: DocumentBase) -> DocumentOut:
    doc = DocumentOut(id="doc-1", version=1, **payload.model_dump())
    _DOCUMENTS[doc.id] = doc
    return doc


@router.get("/{doc_id}", response_model=DocumentOut, dependencies=[Depends(RBACGuard(["viewer", "editor", "admin"]))])
def get_document(doc_id: str) -> DocumentOut:
    if doc_id not in _DOCUMENTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _DOCUMENTS[doc_id]
