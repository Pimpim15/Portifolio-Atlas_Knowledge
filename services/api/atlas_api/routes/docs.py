"""CRUD de documentos."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import Document, DocumentVersion, ReindexJob, ReindexJobItem, ReindexJobStatus
from ..deps import CurrentUser, RBACGuard, get_db, get_redis
from ..observability.metrics import REINDEX_JOB_COUNT
from ..queue.publisher import enqueue_delete, enqueue_index, enqueue_reindex_document
from ..security.idempotency import build_idempotency_context
from ..security.ratelimit import init_rate_limiter

router = APIRouter()
settings = get_settings()
limiter = init_rate_limiter()


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
@limiter.limit(settings.rate_limit_mutation)
async def create_document(
    payload: DocumentBase,
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard(["editor", "admin"])),
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
) -> DocumentOut:
    idem_context = await build_idempotency_context(request, redis, str(current_user.id))
    replay = idem_context.replay_if_available()
    if replay is not None:
        return replay

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
    await session.flush()
    session.add(
        DocumentVersion(
            document_id=doc.id,
            version=doc.version,
            title=doc.title,
            body=doc.body,
            tags=doc.tags,
            created_by=current_user.id,
        )
    )
    await session.commit()
    await session.refresh(doc)
    enqueue_index(doc)
    document_out = DocumentOut.model_validate(doc)
    idem_context.store_response(document_out, status_code=status.HTTP_200_OK)
    return document_out


class DocumentUpdate(DocumentBase):
    pass


@router.put("/{doc_id}", response_model=DocumentOut)
@limiter.limit(settings.rate_limit_mutation)
async def update_document(
    doc_id: uuid.UUID,
    payload: DocumentUpdate,
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard(["editor", "admin"])),
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
) -> DocumentOut:
    idem_context = await build_idempotency_context(request, redis, str(current_user.id))
    replay = idem_context.replay_if_available()
    if replay is not None:
        return replay

    stmt = select(Document).where(
        Document.id == doc_id,
        Document.org_id.in_(current_user.organization_ids),
        Document.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.title = payload.title
    doc.body = payload.body
    doc.tags = payload.tags
    doc.version += 1
    doc.updated_by = current_user.id
    doc.updated_at = datetime.utcnow()

    await session.flush()
    session.add(
        DocumentVersion(
            document_id=doc.id,
            version=doc.version,
            title=doc.title,
            body=doc.body,
            tags=doc.tags,
            created_by=current_user.id,
        )
    )
    await session.commit()
    await session.refresh(doc)
    enqueue_index(doc)
    document_out = DocumentOut.model_validate(doc)
    idem_context.store_response(document_out, status_code=status.HTTP_200_OK)
    return document_out


class ReindexJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ReindexJobStatus
    total_documents: int | None
    processed_documents: int
    created_at: datetime
    updated_at: datetime


@router.post("/reindex", response_model=ReindexJobOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.rate_limit_mutation)
async def trigger_reindex(
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard(["admin"])),
    session: AsyncSession = Depends(get_db),
) -> ReindexJobOut:
    org_id = current_user.organization_ids[0]
    stmt = select(Document).where(
        Document.org_id == org_id,
        Document.deleted_at.is_(None),
    )
    docs_result = await session.execute(stmt)
    documents = docs_result.scalars().all()
    total = len(documents)

    job_status = ReindexJobStatus.RUNNING if total else ReindexJobStatus.SUCCESS
    job = ReindexJob(
        org_id=org_id,
        status=job_status,
        total_documents=total,
        processed_documents=0,
    )
    session.add(job)
    await session.flush()

    for doc in documents:
        session.add(
            ReindexJobItem(
                job_id=job.id,
                document_id=doc.id,
                version=doc.version,
                status=ReindexJobStatus.SUCCESS,
            )
        )

    if total:
        job.processed_documents = total
        job.status = ReindexJobStatus.SUCCESS

    await session.commit()

    for doc in documents:
        enqueue_reindex_document(str(job.id), doc)

    REINDEX_JOB_COUNT.labels(status=job.status.value).inc()
    return ReindexJobOut.model_validate(job)


@router.get("/reindex", response_model=list[ReindexJobOut])
@limiter.limit(settings.rate_limit_default)
async def list_reindex_jobs(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(RBACGuard(["admin"])),
    session: AsyncSession = Depends(get_db),
) -> list[ReindexJobOut]:
    stmt = (
        select(ReindexJob)
        .where(ReindexJob.org_id.in_(current_user.organization_ids))
        .order_by(ReindexJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    jobs = result.scalars().all()
    return [ReindexJobOut.model_validate(job) for job in jobs]


@router.get("/{doc_id}", response_model=DocumentOut)
@limiter.limit(settings.rate_limit_default)
async def get_document(
    doc_id: uuid.UUID,
    request: Request,
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


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.rate_limit_mutation)
async def delete_document(
    doc_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard(["editor", "admin"])),
    session: AsyncSession = Depends(get_db),
    redis = Depends(get_redis),
) -> Response:
    idem_context = await build_idempotency_context(request, redis, str(current_user.id))
    replay = idem_context.replay_if_available()
    if replay is not None:
        return replay

    stmt = select(Document).where(
        Document.id == doc_id,
        Document.org_id.in_(current_user.organization_ids),
        Document.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.deleted_at = datetime.utcnow()
    doc.updated_by = current_user.id

    await session.commit()
    enqueue_delete(str(doc.id), str(doc.org_id))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    idem_context.store_response(None, status_code=response.status_code)
    return response


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    title: str
    body: str
    tags: list[str]
    created_at: datetime
    created_by: uuid.UUID | None


@router.get("/{doc_id}/versions", response_model=list[DocumentVersionOut])
@limiter.limit(settings.rate_limit_default)
async def list_document_versions(
    doc_id: uuid.UUID,
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(RBACGuard(["viewer", "editor", "admin"])),
    session: AsyncSession = Depends(get_db),
) -> list[DocumentVersionOut]:
    stmt = (
        select(DocumentVersion)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(
            DocumentVersion.document_id == doc_id,
            Document.org_id.in_(current_user.organization_ids),
        )
        .order_by(DocumentVersion.version.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()
    return [DocumentVersionOut.model_validate(version) for version in versions]


