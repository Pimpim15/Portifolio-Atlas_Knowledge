"""Rotas de autenticação."""

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..config import get_settings
from ..security.jwt import create_access_token, create_refresh_token

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenPair(BaseModel):
    access: str
    refresh: str
    expires_at: datetime


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest) -> TokenPair:
    settings = get_settings()

    if payload.email != "admin@acme.com" or payload.password != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    subject = str(uuid.uuid4())
    access_token = create_access_token(sub=subject, email=payload.email)
    refresh_token = create_refresh_token(sub=subject)

    return TokenPair(
        access=access_token,
        refresh=refresh_token,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.access_token_ttl_minutes),
    )
