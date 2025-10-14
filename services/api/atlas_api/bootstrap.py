"""Rotinas de inicialização da aplicação."""

from __future__ import annotations

from textwrap import dedent

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db.base import Base
from .db.models import Document, Membership, Organization, RoleEnum, User
from .deps import SessionLocal, engine
from .security.passwords import hash_password


async def init_application() -> None:
    """Cria estruturas básicas e dados seed para ambiente local."""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await _ensure_seed_data(session)


async def _ensure_seed_data(session: AsyncSession) -> None:
    existing = await session.execute(select(User).where(User.email == "admin@acme.com"))
    user = existing.scalar_one_or_none()
    if user is not None:
        return

    org = Organization(name="Acme Corp")
    admin_user = User(email="admin@acme.com", password_hash=hash_password("admin"))
    membership = Membership(user=admin_user, organization=org, role=RoleEnum.ADMIN)

    session.add_all([org, admin_user, membership])
    await session.flush()

    documents = [
        Document(
            org_id=org.id,
            title="Runbook - Incidentes P1",
            body=dedent(
                """
                ## Resumo
                Procedimento oficial para resolução de incidentes prioritários (P1) na Acme Corp.

                ### Passo a passo
                1. Acione o time on-call via PagerDuty.
                2. Reúna informações iniciais: métricas, logs e impacto.
                3. Inicie a ponte de comando.
                4. Documente ações em tempo real no Slack #incidentes.
                5. Assim que normalizado, abra ação post-mortem no Atlas.
                """
            ).strip(),
            tags=["incidentes", "runbook", "p1"],
            created_by=admin_user.id,
            updated_by=admin_user.id,
        ),
        Document(
            org_id=org.id,
            title="Política de Backup RDS",
            body=dedent(
                """
                ## Política
                Backups automáticos executados diariamente às 02h00 UTC com retenção de 30 dias.

                ### Testes de restauração
                - Dev: semanalmente
                - Produção: trimestralmente com auditoria conjunta.

                ### Contatos
                - DBA responsável: dba@acme.com
                - Gestor de continuidade: continuidade@acme.com
                """
            ).strip(),
            tags=["políticas", "rds", "backup"],
            created_by=admin_user.id,
            updated_by=admin_user.id,
        ),
    ]

    session.add_all(documents)
    await session.commit()
