"""Script para povoar o ambiente local com dados iniciais."""

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.api.atlas_api.config import get_settings
from services.api.atlas_api.db.models import Document, Membership, Organization, RoleEnum, User
from services.api.atlas_api.security.passwords import hash_password


async def seed() -> None:
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:  # type: AsyncSession
        await _seed_data(session)


async def _seed_data(session: AsyncSession) -> None:
    org = Organization(name="Acme Corp")
    admin = User(email="admin@acme.com", password_hash=hash_password("admin"))
    membership = Membership(user=admin, organization=org, role=RoleEnum.ADMIN)
    doc = Document(title="Runbook P1", body="Conteúdo inicial", tags=["incidente", "rds"], organization=org)
    session.add_all([org, admin, membership, doc])
    await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
