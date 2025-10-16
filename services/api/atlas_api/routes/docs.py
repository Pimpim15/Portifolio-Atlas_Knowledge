"""CRUD de documentos."""

import base64
import binascii
import time
import uuid
from collections import Counter
from collections.abc import Sequence
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db.models import (
    Document,
    DocumentVersion,
    ReindexJob,
    ReindexJobItem,
    ReindexJobStatus,
    User,
)
from ..deps import CurrentUser, RBACGuard, get_db, get_redis
from ..observability.logging import get_logger
from ..observability.metrics import REINDEX_JOB_COUNT, REINDEX_JOB_LATENCY
from ..queue.publisher import enqueue_delete, enqueue_index, enqueue_reindex_document
from ..reindex.progress import update_reindex_metrics
from ..security.idempotency import build_idempotency_context
from ..security.ratelimit import init_rate_limiter

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    trace = None

router = APIRouter()
settings = get_settings()
limiter = init_rate_limiter()
logger = get_logger(component="api", module="docs")
tracer = trace.get_tracer("atlas-api.docs") if trace else None


def _encode_cursor(item: ReindexJobItem) -> str:
    raw = f"{item.created_at.isoformat()}|{item.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    padding = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode(f"{cursor}{padding}").decode("utf-8")
        created_at_raw, item_id_raw = decoded.split("|", 1)
        created_at = datetime.fromisoformat(created_at_raw)
        return created_at, uuid.UUID(item_id_raw)
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from None


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
    pending_items: int
    running_items: int
    success_items: int
    failed_items: int
    error_message: str | None


def _default_counts() -> dict[ReindexJobStatus, int]:
    return {
        ReindexJobStatus.PENDING: 0,
        ReindexJobStatus.RUNNING: 0,
        ReindexJobStatus.SUCCESS: 0,
        ReindexJobStatus.FAILED: 0,
    }


async def _collect_job_item_counts(
    session: AsyncSession,
    job_ids: Sequence[uuid.UUID],
) -> dict[uuid.UUID, dict[ReindexJobStatus, int]]:
    if not job_ids:
        return {}

    stmt = (
        select(ReindexJobItem.job_id, ReindexJobItem.status, func.count())
        .where(ReindexJobItem.job_id.in_(job_ids))
        .group_by(ReindexJobItem.job_id, ReindexJobItem.status)
    )
    result = await session.execute(stmt)

    counts_map: dict[uuid.UUID, dict[ReindexJobStatus, int]] = {
        job_id: _default_counts().copy() for job_id in job_ids
    }

    for job_id, item_status, count in result.all():
        job_counts = counts_map.setdefault(job_id, _default_counts().copy())
        job_counts[item_status] = int(count)

    return counts_map


def _serialize_job(
    job: ReindexJob,
    counts_map: dict[uuid.UUID, dict[ReindexJobStatus, int]] | None = None,
) -> ReindexJobOut:
    counts = counts_map.get(job.id) if counts_map else None
    if counts is None:
        counts = _default_counts()

    return ReindexJobOut(
        id=job.id,
        status=job.status,
        total_documents=job.total_documents,
        processed_documents=job.processed_documents,
        created_at=job.created_at,
        updated_at=job.updated_at,
        pending_items=counts.get(ReindexJobStatus.PENDING, 0),
        running_items=counts.get(ReindexJobStatus.RUNNING, 0),
        success_items=counts.get(ReindexJobStatus.SUCCESS, 0),
        failed_items=counts.get(ReindexJobStatus.FAILED, 0),
        error_message=job.error_message,
    )


class ReindexJobItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    document_id: uuid.UUID
    version: int
    status: ReindexJobStatus
    created_at: datetime
    updated_at: datetime
    error_message: str | None


class ReindexJobItemsPage(BaseModel):
    items: list[ReindexJobItemOut]
    next_cursor: str | None


class DocumentStatsTotals(BaseModel):
    documents: int
    versions: int
    unique_tags: int
    active_authors: int
    avg_tags_per_document: float


class DocumentStatsTag(BaseModel):
    tag: str
    count: int


class DocumentStatsAuthor(BaseModel):
    author_id: uuid.UUID | None
    display_name: str
    count: int


class DocumentStatsSeriesPoint(BaseModel):
    date: date
    count: int


class DocumentStatsRecentDocument(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    tags: list[str]
    author: str | None


class DocumentStatsResponse(BaseModel):
    totals: DocumentStatsTotals
    top_tags: list[DocumentStatsTag]
    top_authors: list[DocumentStatsAuthor]
    documents_by_day: list[DocumentStatsSeriesPoint]
    recent_documents: list[DocumentStatsRecentDocument]


@router.post("/reindex", response_model=ReindexJobOut, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.rate_limit_mutation)
async def trigger_reindex(
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard(["admin"])),
    session: AsyncSession = Depends(get_db),
) -> ReindexJobOut:
    org_id = current_user.organization_ids[0]
    tracer_cm = (
        tracer.start_as_current_span(
            "docs.trigger_reindex",
            attributes={
                "atlas.reindex.org_id": str(org_id),
            },
        )
        if tracer
        else nullcontext()
    )

    job_status_value = ReindexJobStatus.PENDING.value
    response_payload: ReindexJobOut | None = None
    total = 0
    start = time.perf_counter()

    with tracer_cm as span:
        stmt = select(Document).where(
            Document.org_id == org_id,
            Document.deleted_at.is_(None),
        )
        docs_result = await session.execute(stmt)
        documents = list(docs_result.scalars())
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

        job_items: list[ReindexJobItem] = []
        for doc in documents:
            item = ReindexJobItem(
                job_id=job.id,
                document_id=doc.id,
                version=doc.version,
                status=ReindexJobStatus.PENDING,
            )
            session.add(item)
            job_items.append(item)

        await session.flush()

        if not total:
            job.processed_documents = 0

        await session.commit()
        await session.refresh(job)
        await update_reindex_metrics(session)

        job_status_value = job.status.value

    for doc, item in zip(documents, job_items, strict=False):
        enqueue_reindex_document(str(job.id), doc, str(item.id))

        logger.info(
            "reindex_job_enqueued",
            job_id=str(job.id),
            org_id=str(org_id),
            total_documents=total,
            status=job.status.value,
        )

        if span is not None:
            span.set_attribute("atlas.reindex.job_id", str(job.id))
            span.set_attribute("atlas.reindex.total_documents", total)
            span.set_attribute("atlas.reindex.job_status", job.status.value)
            span.add_event(
                "reindex_enqueued",
                {
                    "atlas.reindex.document_count": total,
                },
            )

        counts_map = await _collect_job_item_counts(session, [job.id])
        response_payload = _serialize_job(job, counts_map)

    duration = time.perf_counter() - start
    if total:
        REINDEX_JOB_COUNT.labels(status=ReindexJobStatus.RUNNING.value).inc()
    else:
        REINDEX_JOB_COUNT.labels(status=ReindexJobStatus.SUCCESS.value).inc()
    REINDEX_JOB_LATENCY.labels(status=job_status_value).observe(duration)

    if response_payload is None:  # pragma: no cover - defensive
        raise RuntimeError("Failed to create reindex job")

    return response_payload


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

    counts_map = await _collect_job_item_counts(session, [job.id for job in jobs])
    return [_serialize_job(job, counts_map) for job in jobs]


@router.get("/reindex/{job_id}/items", response_model=ReindexJobItemsPage)
@limiter.limit(settings.rate_limit_default)
async def list_reindex_job_items(
    job_id: uuid.UUID,
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    cursor: str | None = Query(None),
    current_user: CurrentUser = Depends(RBACGuard(["admin"])),
    session: AsyncSession = Depends(get_db),
) -> ReindexJobItemsPage:
    tracer_cm = (
        tracer.start_as_current_span(
            "docs.list_reindex_job_items",
            attributes={
                "atlas.reindex.job_id": str(job_id),
                "atlas.reindex.limit": limit,
            },
        )
        if tracer
        else nullcontext()
    )

    with tracer_cm as span:
        job_stmt = select(ReindexJob).where(
            ReindexJob.id == job_id,
            ReindexJob.org_id.in_(current_user.organization_ids),
        )
        job_result = await session.execute(job_stmt)
        job = job_result.scalar_one_or_none()
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reindex job not found")

        cursor_filter = None
        if cursor:
            created_at_cursor, item_id_cursor = _decode_cursor(cursor)
            cursor_filter = or_(
                ReindexJobItem.created_at < created_at_cursor,
                and_(
                    ReindexJobItem.created_at == created_at_cursor,
                    ReindexJobItem.id < item_id_cursor,
                ),
            )

        stmt = (
            select(ReindexJobItem)
            .where(ReindexJobItem.job_id == job_id)
            .order_by(ReindexJobItem.created_at.desc(), ReindexJobItem.id.desc())
            .limit(limit + 1)
        )
        if cursor_filter is not None:
            stmt = stmt.where(cursor_filter)

        result = await session.execute(stmt)
        items = list(result.scalars())
        has_more = len(items) > limit
        page_items = items[:limit]

        next_cursor = None
        if page_items and has_more:
            next_cursor = _encode_cursor(page_items[-1])

        payload = ReindexJobItemsPage(
            items=[ReindexJobItemOut.model_validate(item) for item in page_items],
            next_cursor=next_cursor,
        )

        logger.debug(
            "reindex_job_items_listed",
            job_id=str(job_id),
            returned=len(payload.items),
            has_more=has_more,
        )

        if span is not None:
            span.set_attribute("atlas.reindex.items_returned", len(payload.items))
            span.set_attribute("atlas.reindex.has_more", has_more)

        return payload


@router.get("/stats", response_model=DocumentStatsResponse)
@limiter.limit(settings.rate_limit_default)
async def get_documents_stats(
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard(["viewer", "editor", "admin"])),
    session: AsyncSession = Depends(get_db),
) -> DocumentStatsResponse:
    docs_stmt = (
        select(Document)
        .where(
            Document.org_id.in_(current_user.organization_ids),
            Document.deleted_at.is_(None),
        )
        .order_by(Document.created_at.desc())
    )
    docs_result = await session.execute(docs_stmt)
    documents = docs_result.scalars().all()

    total_docs = len(documents)
    tag_counter: Counter[str] = Counter()
    author_counter: Counter[uuid.UUID | None] = Counter()
    series_counter: Counter[date] = Counter()

    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=29)

    for doc in documents:
        tags = doc.tags or []
        tag_counter.update(tags)
        author_counter.update([doc.created_by])

        created_at = doc.created_at
        if created_at is None:
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        created_day = created_at.astimezone(UTC).date()
        if created_day >= start_date:
            series_counter.update([created_day])

    unique_tags = len(tag_counter)
    active_authors_ids = {author_id for author_id in author_counter if author_id is not None}

    versions_stmt = (
        select(func.count(DocumentVersion.id))
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(
            Document.org_id.in_(current_user.organization_ids),
            Document.deleted_at.is_(None),
        )
    )
    versions_result = await session.execute(versions_stmt)
    total_versions = int(versions_result.scalar_one() or 0)

    avg_tags_per_doc = 0.0
    if total_docs:
        avg_tags_per_doc = round(sum(len(doc.tags or []) for doc in documents) / total_docs, 2)

    users_map: dict[uuid.UUID, str] = {}
    if active_authors_ids:
        users_stmt = select(User.id, User.email).where(User.id.in_(active_authors_ids))
        users_result = await session.execute(users_stmt)
        users_map = {row.id: row.email for row in users_result}

    top_tags = [
        DocumentStatsTag(tag=tag, count=count)
        for tag, count in tag_counter.most_common(8)
    ]

    def _author_label(author_id: uuid.UUID | None) -> str:
        if author_id is None:
            return "Desconhecido"
        return users_map.get(author_id, "Desconhecido")

    sorted_authors = sorted(
        (
            (author_id, count)
            for author_id, count in author_counter.items()
            if count > 0
        ),
        key=lambda item: (item[1], _author_label(item[0])),
        reverse=True,
    )

    top_authors = [
        DocumentStatsAuthor(
            author_id=author_id,
            display_name=_author_label(author_id),
            count=count,
        )
        for author_id, count in sorted_authors[:8]
    ]

    series = [
        DocumentStatsSeriesPoint(date=day, count=series_counter.get(day, 0))
        for day in (start_date + timedelta(days=offset) for offset in range(0, 30))
    ]

    recent_documents = [
        DocumentStatsRecentDocument(
            id=doc.id,
            title=doc.title,
            created_at=doc.created_at,
            tags=doc.tags or [],
            author=_author_label(doc.created_by),
        )
        for doc in documents[:5]
    ]

    totals = DocumentStatsTotals(
        documents=total_docs,
        versions=total_versions,
        unique_tags=unique_tags,
        active_authors=len(active_authors_ids),
        avg_tags_per_document=avg_tags_per_doc,
    )

    return DocumentStatsResponse(
        totals=totals,
        top_tags=top_tags,
        top_authors=top_authors,
        documents_by_day=series,
        recent_documents=recent_documents,
    )


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


