"""Integration tests for token revocation."""

from __future__ import annotations

import pyotp
from fastapi.testclient import TestClient


def _login(client: TestClient) -> tuple[str, str]:
    totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
    response = client.post(
        "/auth/login",
        json={"email": "admin@acme.com", "password": "admin", "mfa_code": totp.now()},
    )
    assert response.status_code == 200, response.json()
    payload = response.json()
    return payload["access"], payload["refresh"]


def test_logout_revokes_access_token(client: TestClient) -> None:
    access_token, refresh_token = _login(client)

    headers = {"Authorization": f"Bearer {access_token}"}

    profile_response = client.get("/users/me", headers=headers)
    assert profile_response.status_code == 200

    logout_response = client.post("/auth/logout", json={"refresh": refresh_token}, headers=headers)
    assert logout_response.status_code == 204

    replay_response = client.get("/users/me", headers=headers)
    assert replay_response.status_code == 401