"""Rotas de autenticação."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..config import get_settings
from ..db.models import User
from ..deps import get_db
from ..security.jwt import create_access_token, create_refresh_token
from ..security.passwords import verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenPair(BaseModel):
    access: str
    refresh: str
    expires_at: datetime


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenPair:
    settings = get_settings()

    result = await session.execute(
        select(User).options(joinedload(User.memberships)).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    memberships = user.memberships
    if not memberships:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no organization access")

    roles = [membership.role.value for membership in memberships]
    org_ids = [str(membership.org_id) for membership in memberships]

    access_token = create_access_token(sub=str(user.id), email=user.email, roles=roles, organization_ids=org_ids)
    refresh_token = create_refresh_token(sub=str(user.id))

    expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_ttl_minutes)

    return TokenPair(access=access_token, refresh=refresh_token, expires_at=expires_at)
