"""Tests para utilitários de progresso de reindex."""

from __future__ import annotations

from datetime import datetime
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.atlas_api.reindex import progress


@pytest.mark.asyncio
async def test_mark_job_item_retry_moves_item_back_to_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    item_id = uuid.uuid4()

    fake_item = AsyncMock()
    fake_item.status = progress.ReindexJobStatus.RUNNING
    fake_item.error_message = None
    fake_item.job_id = job_id

    fake_job = AsyncMock()
    fake_job.id = job_id
    fake_job.status = progress.ReindexJobStatus.RUNNING
    fake_job.processed_documents = 1

    async def fake_load_job_item(session: AsyncSession, job: uuid.UUID, item: uuid.UUID):  # noqa: ANN001
        assert job == job_id
        assert item == item_id
        return fake_item

    async def fake_session_get(model, pk):  # type: ignore[override]
        assert model is progress.ReindexJob
        assert pk == job_id
        return fake_job

    async def fake_refresh_processed(session: AsyncSession, job):  # noqa: ANN001
        assert job is fake_job
        job.processed_documents = 0

    spy_metrics = AsyncMock()

    monkeypatch.setattr(progress, "_load_job_item", fake_load_job_item)
    monkeypatch.setattr(progress, "_refresh_processed_count", fake_refresh_processed)
    monkeypatch.setattr(progress, "_update_reindex_metrics", spy_metrics)

    async def fake_with_session(callback):  # type: ignore[override]
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=fake_session_get)
        await callback(mock_session)

    monkeypatch.setattr(progress, "_with_session", fake_with_session)

    await progress._mark_job_item_retry_async(job_id, item_id, "transient_error")

    assert fake_item.status == progress.ReindexJobStatus.PENDING
    assert fake_item.error_message == "transient_error"
    assert fake_job.status == progress.ReindexJobStatus.RUNNING
    assert fake_job.processed_documents == 0
    spy_metrics.assert_awaited()