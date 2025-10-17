"""Rotinas de inicialização da aplicação."""

from __future__ import annotations

from textwrap import dedent

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db.base import Base
from .db.models import Document, DocumentVersion, Membership, Organization, RoleEnum, User
from .deps import SessionLocal, engine
from .observability.logging import get_logger
from .search.mappings import DOC_INDEX
from .search.os_client import ensure_index_exists, get_client
from .security.mfa import bootstrap_admin_mfa_secret
from .security.passwords import hash_password, verify_password

logger = get_logger(component="api", module="bootstrap")


async def init_application() -> None:
    """Cria estruturas básicas e dados seed para ambiente local."""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await _ensure_seed_data(session)
    _ensure_search_index()


async def _ensure_seed_data(session: AsyncSession) -> None:
    org_result = await session.execute(select(Organization).where(Organization.name == "Acme Corp"))
    org = org_result.scalar_one_or_none()
    if org is None:
        org = Organization(name="Acme Corp")
        session.add(org)
        await session.flush()

    user_result = await session.execute(select(User).where(User.email == "admin@acme.com"))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(email="admin@acme.com", password_hash=hash_password("admin"), is_active=True)
        session.add(user)
        await session.flush()
    else:
        if not verify_password("admin", user.password_hash):
            user.password_hash = hash_password("admin")
        user.is_active = True

    bootstrap_admin_mfa_secret(user)

    membership_result = await session.execute(
        select(Membership).where(and_(Membership.user_id == user.id, Membership.org_id == org.id))
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        membership = Membership(user_id=user.id, org_id=org.id, role=RoleEnum.ADMIN)
        session.add(membership)

    seed_documents = [
        {
            "title": "Runbook - Incidentes P1",
            "body": dedent(
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
            "tags": ["incidentes", "runbook", "p1"],
        },
        {
            "title": "Política de Backup RDS",
            "body": dedent(
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
            "tags": ["políticas", "rds", "backup"],
        },
    ]

    for spec in seed_documents:
        existing_doc = await session.execute(
            select(Document).where(and_(Document.org_id == org.id, Document.title == spec["title"]))
        )
        if existing_doc.scalar_one_or_none() is not None:
            continue

        doc = Document(
            org_id=org.id,
            title=spec["title"],
            body=spec["body"],
            tags=spec["tags"],
            created_by=user.id,
            updated_by=user.id,
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
                created_by=user.id,
            )
        )

    await session.commit()


def _ensure_search_index() -> None:
    try:
        client = get_client()
        ensure_index_exists(client, DOC_INDEX)
    except Exception:  # pragma: no cover - infra dependency
        logger.exception("search_index_bootstrap_failed")
