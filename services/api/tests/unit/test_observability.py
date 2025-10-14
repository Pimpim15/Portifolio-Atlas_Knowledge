"""Testes para instrumentação de observabilidade."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_request_id_and_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "x-request-id" in response.headers

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    assert "atlas_request_total" in metrics_response.text
