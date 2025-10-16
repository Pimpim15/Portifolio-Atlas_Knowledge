"""Tests para o módulo de limpeza de reindex."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.atlas_api.db.base import Base
from services.api.atlas_api.db.models import (
    Organization,
    ReindexJob,
    ReindexJobItem,
    ReindexJobStatus,
)
from services.api.atlas_api.reindex import cleanup


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


def _make_job(
    *,
    org: Organization,
    status: ReindexJobStatus,
    total_documents: int | None,
    processed_documents: int,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    error_message: str | None = None,
) -> ReindexJob:
    job = ReindexJob(
        organization=org,
        status=status,
        total_documents=total_documents,
        processed_documents=processed_documents,
        error_message=error_message,
    )
    now = datetime.utcnow()
    job.created_at = created_at or now
    job.updated_at = updated_at or now
    return job


def _make_item(
    *,
    job: ReindexJob,
    status: ReindexJobStatus,
    version: int,
    error_message: str | None = None,
) -> ReindexJobItem:
    return ReindexJobItem(
        job=job,
        document_id=uuid.uuid4(),
        version=version,
        status=status,
        error_message=error_message,
    )


@pytest.mark.asyncio
async def test_repair_marks_success_when_all_items_completed(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    org = Organization(name="Org")
    job = _make_job(
        org=org,
        status=ReindexJobStatus.RUNNING,
        total_documents=2,
        processed_documents=1,
        error_message="transient_error",
    )
    _make_item(job=job, status=ReindexJobStatus.SUCCESS, version=1)
    _make_item(job=job, status=ReindexJobStatus.SUCCESS, version=2)
    session.add(org)
    await session.commit()

    metrics_spy = AsyncMock()
    monkeypatch.setattr(cleanup, "update_reindex_metrics", metrics_spy)

    summary = await cleanup.repair_reindex_jobs(
        session,
        stale_after=timedelta(minutes=5),
        mark_as_failed_reason="stale_items",
    )

    await session.refresh(job)

    assert summary.marked_success == 1
    assert summary.updated_jobs == 1
    assert job.status == ReindexJobStatus.SUCCESS
    assert job.error_message is None
    assert job.processed_documents == 2
    metrics_spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_repair_marks_failed_when_items_are_stale(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    org = Organization(name="Org")
    stale_timestamp = datetime.utcnow() - timedelta(hours=2)
    job = _make_job(
        org=org,
        status=ReindexJobStatus.RUNNING,
        total_documents=3,
        processed_documents=1,
        created_at=stale_timestamp,
        updated_at=stale_timestamp,
    )
    _make_item(job=job, status=ReindexJobStatus.SUCCESS, version=1)
    pending = _make_item(job=job, status=ReindexJobStatus.PENDING, version=2)
    _make_item(job=job, status=ReindexJobStatus.PENDING, version=3)
    session.add(org)
    await session.commit()

    metrics_spy = AsyncMock()
    monkeypatch.setattr(cleanup, "update_reindex_metrics", metrics_spy)

    summary = await cleanup.repair_reindex_jobs(
        session,
        stale_after=timedelta(minutes=30),
        mark_as_failed_reason="worker_timeout",
    )

    await session.refresh(job)
    await session.refresh(pending)
    items = (
        await session.execute(select(ReindexJobItem).where(ReindexJobItem.job_id == job.id))
    ).scalars().all()

    assert summary.marked_failed == 1
    assert summary.items_marked_failed == 2
    assert job.status == ReindexJobStatus.FAILED
    assert job.error_message == "worker_timeout"
    assert pending.status == ReindexJobStatus.FAILED
    assert pending.error_message == "worker_timeout"
    assert sum(1 for item in items if item.status == ReindexJobStatus.FAILED) == 2
    assert sum(1 for item in items if item.status == ReindexJobStatus.SUCCESS) == 1
    metrics_spy.assert_awaited_once()


@pytest.mark.asyncio
async def test_repair_dry_run_does_not_mutate(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    org = Organization(name="Org")
    job = _make_job(
        org=org,
        status=ReindexJobStatus.PENDING,
        total_documents=1,
        processed_documents=0,
    )
    session.add(org)
    await session.commit()

    metrics_spy = AsyncMock()
    monkeypatch.setattr(cleanup, "update_reindex_metrics", metrics_spy)

    summary = await cleanup.repair_reindex_jobs(
        session,
        stale_after=timedelta(minutes=30),
        mark_as_failed_reason="worker_timeout",
        apply=False,
    )

    await session.refresh(job)

    assert summary.inspected_jobs == 1
    assert summary.marked_failed == 0
    assert job.status == ReindexJobStatus.PENDING
    metrics_spy.assert_not_called()