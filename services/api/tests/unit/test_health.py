from services.api.atlas_api.main import app


def test_health_check(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
