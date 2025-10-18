"""Rotas de autenticação."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from redis import Redis

from ..config import get_settings
from ..db.models import User
from ..deps import CurrentUser, RBACGuard, decode_token, get_current_user, get_db, get_redis
from ..security.jwt import create_access_token, create_refresh_token
from ..security.mfa import build_provisioning_uri, generate_mfa_secret, requires_mfa, verify_mfa_code
from ..security.passwords import verify_password
from ..security.ratelimit import init_rate_limiter
from ..security.token_revocation import mark_token_revoked

router = APIRouter()
settings = get_settings()
limiter = init_rate_limiter()


class LoginRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


class TokenPair(BaseModel):
    access: str
    refresh: str
    expires_at: datetime


class LogoutRequest(BaseModel):
    refresh: str | None = None


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    issuer: str


class MFAActivateRequest(BaseModel):
    code: str


@router.post("/login", response_model=TokenPair)
@limiter.limit(settings.rate_limit_auth)
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:

    result = await session.execute(
        select(User).options(joinedload(User.memberships)).where(User.email == payload.email)
    )
    user = result.unique().scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    memberships = user.memberships
    if not memberships:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User has no organization access")

    roles = [membership.role.value for membership in memberships]
    org_ids = [str(membership.org_id) for membership in memberships]

    if requires_mfa(user):
        verify_mfa_code(user, payload.mfa_code)

    access_token, _ = create_access_token(sub=str(user.id), email=user.email, roles=roles, organization_ids=org_ids)
    refresh_token, _ = create_refresh_token(sub=str(user.id))

    expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_ttl_minutes)

    return TokenPair(access=access_token, refresh=refresh_token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    payload: LogoutRequest | None = None,
    _current_user: CurrentUser = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> Response:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    access_token = auth_header.split(" ", 1)[1].strip()
    access_payload = decode_token(access_token)
    access_jti = access_payload.get("jti")
    access_exp = access_payload.get("exp")
    if not access_jti or not access_exp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid access token payload")
    mark_token_revoked(redis, str(access_jti), int(access_exp))

    if payload and payload.refresh:
        try:
            refresh_payload = decode_token(payload.refresh, expected_type="refresh")
        except HTTPException as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token") from exc

        refresh_jti = refresh_payload.get("jti")
        refresh_exp = refresh_payload.get("exp")
        if refresh_jti and refresh_exp:
            mark_token_revoked(redis, str(refresh_jti), int(refresh_exp))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mfa/setup", response_model=MFASetupResponse)
@limiter.limit(settings.rate_limit_mutation)
async def setup_mfa(
    request: Request,
    current_user: CurrentUser = Depends(RBACGuard([role.lower() for role in settings.admin_mfa_roles])),
    session: AsyncSession = Depends(get_db),
) -> MFASetupResponse:
    user = await session.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    secret = generate_mfa_secret()
    user.mfa_secret = secret
    user.mfa_enabled = False
    await session.commit()

    issuer = settings.jwt_issuer or "Atlas Knowledge"
    provisioning_uri = build_provisioning_uri(secret, email=user.email, issuer=issuer)
    return MFASetupResponse(secret=secret, provisioning_uri=provisioning_uri, issuer=issuer)


@router.post("/mfa/activate", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.rate_limit_mutation)
async def activate_mfa(
    request: Request,
    payload: MFAActivateRequest,
    current_user: CurrentUser = Depends(RBACGuard([role.lower() for role in settings.admin_mfa_roles])),
    session: AsyncSession = Depends(get_db),
) -> Response:
    user = await session.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA setup not initialized")

    verify_mfa_code(user, payload.code)
    user.mfa_enabled = True
    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
