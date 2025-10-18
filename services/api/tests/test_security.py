"""Testes de segurança e conformidade."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Iterator

import pyotp
import pytest
from sqlalchemy import select

from services.api.atlas_api.deps import SessionLocal
from services.api.atlas_api.db.models import Membership, Organization, RoleEnum, User
from services.api.atlas_api.security.passwords import hash_password


@pytest.fixture(autouse=True)
def reset_rate_limiter(client) -> Iterator[None]:
    limiter = getattr(client.app.state, "limiter", None)
    if limiter is not None:
        limiter.reset()
    yield
    if limiter is not None:
        limiter.reset()


async def _create_admin_user(email: str, password: str) -> uuid.UUID:
    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).where(Organization.name == "Acme Corp"))
        if org is None:
            org = Organization(name="Acme Corp")
            session.add(org)
            await session.flush()

        user = User(email=email, password_hash=hash_password(password), is_active=True)
        session.add(user)
        await session.flush()

        membership = Membership(user_id=user.id, org_id=org.id, role=RoleEnum.ADMIN)
        session.add(membership)
        await session.commit()
        return user.id


async def _get_user(user_id: uuid.UUID) -> User | None:
    async with SessionLocal() as session:
        return await session.get(User, user_id)


@pytest.mark.parametrize("header_name,expected", [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"),
    ("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload"),
    ("Permissions-Policy", "geolocation=(), microphone=(), camera=()"),
])
def test_security_headers_applied(client, header_name: str, expected: str) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.headers.get(header_name) == expected


def test_login_rate_limit_enforced(client) -> None:
    payload = {"email": "admin@acme.com", "password": "invalid"}
    for _ in range(10):
        response = client.post("/auth/login", json=payload)
        assert response.status_code == 401

    blocked = client.post("/auth/login", json=payload)
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["detail"] == "Rate limit exceeded"
    assert body["limit"] is not None


def test_mfa_onboarding_flow(client) -> None:
    email = f"security-{uuid.uuid4()}@acme.com"
    password = "Sup3rStr0ng!"
    user_id = asyncio.run(_create_admin_user(email, password))

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    headers = {"Authorization": f"Bearer {tokens['access']}"}

    setup_response = client.post("/auth/mfa/setup", headers=headers)
    assert setup_response.status_code == 200
    setup_payload = setup_response.json()
    secret = setup_payload["secret"]
    assert secret
    assert setup_payload["issuer"]
    assert setup_payload["provisioning_uri"].startswith("otpauth://totp/")

    invalid_activation = client.post(
        "/auth/mfa/activate",
        headers=headers,
        json={"code": "000000"},
    )
    assert invalid_activation.status_code == 401

    totp = pyotp.TOTP(secret)
    valid_code = totp.now()

    activation = client.post(
        "/auth/mfa/activate",
        headers=headers,
        json={"code": valid_code},
    )
    assert activation.status_code == 204

    stored_user = asyncio.run(_get_user(user_id))
    assert stored_user is not None
    assert stored_user.mfa_secret == secret
    assert stored_user.mfa_enabled is True

    without_code = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert without_code.status_code == 401
    assert without_code.json()["detail"] == "MFA code required"

    time.sleep(1)
    login_with_code = client.post(
        "/auth/login",
        json={"email": email, "password": password, "mfa_code": totp.now()},
    )
    assert login_with_code.status_code == 200
