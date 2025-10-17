"""Tests for CORS configuration."""

from __future__ import annotations

from fastapi.testclient import TestClient


ALLOWED_ORIGIN = "http://localhost:5173"


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/healthz",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_cors_blocks_unlisted_origin(client: TestClient) -> None:
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None
