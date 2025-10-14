"""Dependências comuns da API."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import uuid

from fastapi import Depends, Header, status as http_status
from fastapi.exceptions import HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from redis import Redis  # type: ignore[import]

from .config import get_settings
from .db.models import Membership, RoleEnum, User
from .observability.logging import bind_context

settings = get_settings()
engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
_redis_client: Redis | None = None


class CurrentUser(BaseModel):
    id: uuid.UUID
    email: str
    roles: list[str]
    organization_ids: list[uuid.UUID]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=False)
    return _redis_client


async def get_current_user(
    authorization: str = Header(..., convert_underscores=False),
    session: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        raw_audience = settings.jwt_audience
        if isinstance(raw_audience, (list, tuple, set)):
            audience = next(iter(raw_audience), None)
        else:
            audience = raw_audience

        decode_kwargs: dict[str, object] = {
            "algorithms": [settings.jwt_algorithm],
        }
        if audience:
            decode_kwargs["audience"] = audience

        payload = jwt.decode(
            token,
            settings.jwt_public_key,
            **decode_kwargs,  # type: ignore[arg-type]
        )
    except JWTError as exc:  # pragma: no cover - jose já cobre mensagens de erro
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(str(subject))
    except ValueError as exc:
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid subject identifier") from exc

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=http_status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")

    roles = list(map(str, payload.get("roles", [])))
    org_ids_payload = payload.get("org_ids") or payload.get("organization_ids")

    if not roles or not org_ids_payload:
        memberships_result = await session.execute(
            select(Membership.role, Membership.org_id).where(Membership.user_id == user_id)
        )
        roles = []
        org_ids = []
        for membership_role, membership_org in memberships_result.all():
            if isinstance(membership_role, RoleEnum):
                roles.append(membership_role.value)
            else:
                roles.append(str(membership_role))
            org_ids.append(membership_org)
    else:
        org_ids = []
        for raw_org in org_ids_payload:
            try:
                org_ids.append(uuid.UUID(str(raw_org)))
            except ValueError:
                continue

    if not roles:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Roles not assigned")

    if not org_ids:
        memberships_result = await session.execute(
            select(Membership.org_id).where(Membership.user_id == user_id)
        )
        org_ids = [row[0] for row in memberships_result.all()]

    if not org_ids:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="User has no organization access")

    normalized_roles = sorted({role.lower() for role in roles})
    unique_org_ids: list[uuid.UUID] = []
    for org_id in org_ids:
        if org_id not in unique_org_ids:
            unique_org_ids.append(org_id)

    bind_context(
        user_id=str(user.id),
        user_email=user.email,
        user_roles=normalized_roles,
        organization_ids=[str(org_id) for org_id in unique_org_ids],
    )

    return CurrentUser(id=user.id, email=user.email, roles=normalized_roles, organization_ids=unique_org_ids)


class RBACGuard:
    """Valida se o usuário autenticado possui um dos papéis exigidos."""

    def __init__(self, roles: list[str]):
        self.roles = set(roles)

    def __call__(self, user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(user.roles).intersection(self.roles):
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        bind_context(authorized_roles=sorted(self.roles))
        return user
