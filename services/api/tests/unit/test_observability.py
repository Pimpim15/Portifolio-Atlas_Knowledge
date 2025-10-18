"""Testes para instrumentação de observabilidade."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_request_id_and_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in response.headers

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "atlas_request_total" in metrics_response.text


def test_request_id_forwarding(client: TestClient) -> None:
    response = client.get("/healthz", headers={"x-request-id": "req-123"})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == "req-123"
