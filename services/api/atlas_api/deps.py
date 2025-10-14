"""Dependências comuns da API."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi import status as http_status
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_settings = get_settings()
_engine = create_async_engine(str(_settings.database_url), pool_pre_ping=True)
SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


class RBACGuard:
    """Valida se o usuário autenticado possui um dos papéis exigidos."""

    def __init__(self, roles: list[str]):
        self.roles = roles

    def __call__(self, user = Depends(lambda: {"roles": []})):  # type: ignore[no-untyped-def]  # noqa: B008
        user_roles = set(user.get("roles", []))
        if not user_roles.intersection(self.roles):
            raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
