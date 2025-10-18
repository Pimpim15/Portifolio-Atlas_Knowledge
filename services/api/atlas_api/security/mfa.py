"""Helpers para MFA baseado em TOTP."""

from __future__ import annotations

import pyotp
from fastapi import HTTPException, status

from ..config import get_settings
from ..db.models import User


def _user_roles(user: User) -> set[str]:
    return {membership.role.value for membership in user.memberships}


def requires_mfa(user: User) -> bool:
    settings = get_settings()
    if not settings.enforce_admin_mfa:
        return False
    enforced_roles = {role.lower() for role in settings.admin_mfa_roles}
    if not any(role in enforced_roles for role in _user_roles(user)):
        return False
    return bool(user.mfa_enabled and user.mfa_secret)


def verify_mfa_code(user: User, code: str | None) -> None:
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA code required",
        )
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )


def bootstrap_admin_mfa_secret(user: User) -> None:
    settings = get_settings()
    if user.email == "admin@acme.com" and not user.mfa_secret:
        user.mfa_secret = settings.admin_bootstrap_mfa_secret
        user.mfa_enabled = True


def generate_mfa_secret() -> str:
    """Cria um segredo TOTP aleatório para onboarding de MFA."""

    return pyotp.random_base32()  # 160 bits por padrão


def build_provisioning_uri(secret: str, *, email: str, issuer: str) -> str:
    """Gera URI compatível com apps autenticadores (otpauth://)."""

    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)
