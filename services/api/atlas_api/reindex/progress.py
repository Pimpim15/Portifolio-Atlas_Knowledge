"""Helpers para atualizar o progresso de jobs de reindex."""

from __future__ import annotations

import asyncio
import uuid
from typing import Awaitable, Callable

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import ReindexJob, ReindexJobItem, ReindexJobStatus
from ..deps import SessionLocal
from ..observability.logging import get_logger
from ..observability.metrics import REINDEX_JOB_COUNT

logger = get_logger(component="worker", module="reindex_progress")


def _run_async(coro: Awaitable[object]) -> object:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _normalize_uuid(value: uuid.UUID | str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


async def _with_session(callback: Callable[[AsyncSession], Awaitable[None]]) -> None:
    async with SessionLocal() as session:
        await callback(session)


async def _load_job_item(session: AsyncSession, job_id: uuid.UUID, job_item_id: uuid.UUID) -> ReindexJobItem | None:
    item = await session.get(ReindexJobItem, job_item_id)
    if item is None:
        logger.warning(
            "reindex_job_item_not_found",
            job_id=str(job_id),
            job_item_id=str(job_item_id),
        )
        return None
    if item.job_id != job_id:
        logger.warning(
            "reindex_job_item_mismatch",
            job_id=str(job_id),
            job_item_id=str(job_item_id),
            stored_job_id=str(item.job_id),
        )
        return None
    return item


async def _refresh_processed_count(session: AsyncSession, job: ReindexJob) -> None:
    processed_stmt: Select[tuple[int]] = (
        select(func.count())
        .select_from(ReindexJobItem)
        .where(
            ReindexJobItem.job_id == job.id,
            ReindexJobItem.status.in_([ReindexJobStatus.SUCCESS, ReindexJobStatus.FAILED]),
        )
    )
    result = await session.execute(processed_stmt)
    job.processed_documents = int(result.scalar_one())


async def _mark_job_item_started_async(job_id: uuid.UUID, job_item_id: uuid.UUID) -> None:
    async def _handler(session: AsyncSession) -> None:
        item = await _load_job_item(session, job_id, job_item_id)
        if item is None or item.status != ReindexJobStatus.PENDING:
            return
        item.status = ReindexJobStatus.RUNNING
        await session.commit()

    await _with_session(_handler)


async def _mark_job_item_success_async(job_id: uuid.UUID, job_item_id: uuid.UUID) -> None:
    async def _handler(session: AsyncSession) -> None:
        item = await _load_job_item(session, job_id, job_item_id)
        if item is None:
            return
        previous_status = item.status
        item.status = ReindexJobStatus.SUCCESS
        item.error_message = None

        job = await session.get(ReindexJob, job_id)
        if job is None:
            await session.commit()
            return

        await _refresh_processed_count(session, job)

        prev_job_status = job.status
        if job.status != ReindexJobStatus.FAILED:
            total = job.total_documents or 0
            if total == 0 or job.processed_documents >= total:
                job.status = ReindexJobStatus.SUCCESS
            else:
                job.status = ReindexJobStatus.RUNNING

        await session.commit()

        if (
            previous_status != ReindexJobStatus.SUCCESS
            and job.status == ReindexJobStatus.SUCCESS
            and prev_job_status != ReindexJobStatus.SUCCESS
        ):
            REINDEX_JOB_COUNT.labels(status=ReindexJobStatus.SUCCESS.value).inc()

    await _with_session(_handler)


async def _mark_job_item_error_async(job_id: uuid.UUID, job_item_id: uuid.UUID, error_message: str) -> None:
    async def _handler(session: AsyncSession) -> None:
        item = await _load_job_item(session, job_id, job_item_id)
        if item is None:
            return

        item.status = ReindexJobStatus.FAILED
        item.error_message = error_message

        job = await session.get(ReindexJob, job_id)
        if job is None:
            await session.commit()
            return

        await _refresh_processed_count(session, job)

        prev_job_status = job.status
        job.status = ReindexJobStatus.FAILED
        job.error_message = error_message

        await session.commit()

        if prev_job_status != ReindexJobStatus.FAILED:
            REINDEX_JOB_COUNT.labels(status=ReindexJobStatus.FAILED.value).inc()

    await _with_session(_handler)


def mark_job_item_started(job_id: uuid.UUID | str, job_item_id: uuid.UUID | str) -> None:
    job_uuid = _normalize_uuid(job_id)
    item_uuid = _normalize_uuid(job_item_id)
    _run_async(_mark_job_item_started_async(job_uuid, item_uuid))


def mark_job_item_success(job_id: uuid.UUID | str, job_item_id: uuid.UUID | str) -> None:
    job_uuid = _normalize_uuid(job_id)
    item_uuid = _normalize_uuid(job_item_id)
    _run_async(_mark_job_item_success_async(job_uuid, item_uuid))


def mark_job_item_error(job_id: uuid.UUID | str, job_item_id: uuid.UUID | str, error_message: str) -> None:
    job_uuid = _normalize_uuid(job_id)
    item_uuid = _normalize_uuid(job_item_id)
    _run_async(_mark_job_item_error_async(job_uuid, item_uuid, error_message))
