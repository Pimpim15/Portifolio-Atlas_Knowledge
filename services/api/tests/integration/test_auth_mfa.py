"""Tests for MFA protected login."""

from __future__ import annotations

import pyotp
from fastapi.testclient import TestClient


def test_login_requires_mfa_code(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "admin@acme.com", "password": "admin"},
    )
    assert response.status_code == 401
    assert response.json()["detail"].lower().startswith("mfa code")


def test_login_with_invalid_mfa_code(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "admin@acme.com", "password": "admin", "mfa_code": "000000"},
    )
    assert response.status_code == 401
    assert response.json()["detail"].lower().startswith("invalid mfa")


def test_login_with_valid_mfa_code(client: TestClient) -> None:
    totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
    response = client.post(
        "/auth/login",
        json={"email": "admin@acme.com", "password": "admin", "mfa_code": totp.now()},
    )
    assert response.status_code == 200, response.json()
