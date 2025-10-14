"""CRUD de documentos."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Document
from ..deps import CurrentUser, RBACGuard, get_db

router = APIRouter()


class DocumentBase(BaseModel):
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)


class DocumentOut(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    org_id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None


@router.post("", response_model=DocumentOut)
@router.post("/", response_model=DocumentOut, include_in_schema=False)
async def create_document(
    payload: DocumentBase,
    current_user: CurrentUser = Depends(RBACGuard(["editor", "admin"])),
    session: AsyncSession = Depends(get_db),
) -> DocumentOut:
    organization_id = current_user.organization_ids[0]
    doc = Document(
        org_id=organization_id,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    current_user: CurrentUser = Depends(RBACGuard(["viewer", "editor", "admin"])),
    session: AsyncSession = Depends(get_db),
) -> DocumentOut:
    stmt = select(Document).where(
        Document.id == doc_id,
        Document.org_id.in_(current_user.organization_ids),
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentOut.model_validate(doc)
