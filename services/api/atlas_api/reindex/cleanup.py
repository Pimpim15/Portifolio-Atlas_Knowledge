"""Rotinas para reparar jobs de reindex em estado inconsistente."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import ReindexJob, ReindexJobItem, ReindexJobStatus
from ..observability.logging import get_logger
from .progress import update_reindex_metrics

logger = get_logger(component="api", module="reindex_cleanup")


@dataclass(slots=True)
class CleanupSummary:
    inspected_jobs: int = 0
    updated_jobs: int = 0
    marked_success: int = 0
    marked_failed: int = 0
    items_marked_failed: int = 0
    processed_updates: int = 0
    pending_jobs: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "inspected_jobs": self.inspected_jobs,
            "updated_jobs": self.updated_jobs,
            "marked_success": self.marked_success,
            "marked_failed": self.marked_failed,
            "items_marked_failed": self.items_marked_failed,
            "processed_updates": self.processed_updates,
            "pending_jobs": self.pending_jobs,
        }


def _naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


async def _load_active_jobs(session: AsyncSession) -> list[ReindexJob]:
    stmt: Select[ReindexJob] = select(ReindexJob).where(
        ReindexJob.status.in_([
            ReindexJobStatus.PENDING,
            ReindexJobStatus.RUNNING,
        ])
    )
    result = await session.execute(stmt)
    return list(result.scalars())


async def _load_job_items(session: AsyncSession, job_id: uuid.UUID) -> list[ReindexJobItem]:
    stmt: Select[ReindexJobItem] = select(ReindexJobItem).where(ReindexJobItem.job_id == job_id)
    result = await session.execute(stmt)
    return list(result.scalars())


async def repair_reindex_jobs(
    session: AsyncSession,
    *,
    stale_after: timedelta,
    mark_as_failed_reason: str,
    apply: bool = True,
) -> CleanupSummary:
    """Reconcilia jobs de reindex pendentes.

    Quando ``apply`` é ``False`` a função apenas computa o impacto e não altera dados.
    """

    summary = CleanupSummary()
    jobs = await _load_active_jobs(session)
    summary.inspected_jobs = len(jobs)

    if not jobs:
        if not apply:
            await session.rollback()
        return summary

    now = datetime.utcnow()
    cutoff = now - stale_after
    changes_applied = False

    for job in jobs:
        items = await _load_job_items(session, job.id)
        total_items = len(items)
        total_documents = job.total_documents if job.total_documents is not None else total_items

        success_items = sum(1 for item in items if item.status == ReindexJobStatus.SUCCESS)
        failed_items = sum(1 for item in items if item.status == ReindexJobStatus.FAILED)
        pending_items = [item for item in items if item.status == ReindexJobStatus.PENDING]
        running_items = sum(1 for item in items if item.status == ReindexJobStatus.RUNNING)

        processed_count = success_items + failed_items
        new_processed = processed_count

        should_mark_success = False
        should_mark_failed = False
        failure_reason: str | None = None
        items_to_fail: list[ReindexJobItem] = []

        if total_documents is not None and processed_count >= total_documents:
            if failed_items == 0:
                if job.status != ReindexJobStatus.SUCCESS or job.error_message:
                    should_mark_success = True
            else:
                if job.status != ReindexJobStatus.FAILED:
                    should_mark_failed = True
                    failure_reason = job.error_message or "job_contains_failed_items"
        elif pending_items and running_items == 0:
            updated_at = _naive(job.updated_at) or _naive(job.created_at) or now
            if updated_at <= cutoff:
                should_mark_failed = True
                failure_reason = mark_as_failed_reason
                items_to_fail = list(pending_items)
                new_processed = processed_count + len(items_to_fail)
            else:
                summary.pending_jobs += 1
        else:
            if pending_items or running_items:
                summary.pending_jobs += 1

        processed_changed = new_processed != job.processed_documents
        job_updated = False

        if should_mark_success:
            summary.marked_success += 1
            job_updated = True
            if apply:
                job.status = ReindexJobStatus.SUCCESS
                job.error_message = None
                job.processed_documents = new_processed
        elif should_mark_failed:
            summary.marked_failed += 1
            summary.items_marked_failed += len(items_to_fail)
            job_updated = True
            if apply:
                for item in items_to_fail:
                    item.status = ReindexJobStatus.FAILED
                    item.error_message = failure_reason
                job.status = ReindexJobStatus.FAILED
                job.error_message = failure_reason
                job.processed_documents = new_processed
        elif processed_changed:
            job_updated = True
            if apply:
                job.processed_documents = new_processed

        if job_updated:
            summary.updated_jobs += 1
            if processed_changed:
                summary.processed_updates += 1
            if apply:
                changes_applied = True
                logger.info(
                    "reindex_job_repaired",
                    job_id=str(job.id),
                    new_status=job.status.value,
                    processed=new_processed,
                    pending_before=len(pending_items),
                    items_marked_failed=len(items_to_fail),
                    action=(
                        "mark_success"
                        if should_mark_success
                        else "mark_failed" if should_mark_failed else "processed_update"
                    ),
                )

    if apply:
        if changes_applied:
            await session.flush()
            await update_reindex_metrics(session)
            await session.commit()
        else:
            await session.rollback()
    else:
        await session.rollback()

    return summary
