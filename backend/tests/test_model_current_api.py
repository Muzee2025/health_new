from fastapi.testclient import TestClient

from app.main import app


def test_model_current_endpoint_returns_dynamic_model_meta():
    client = TestClient(app)
    resp = client.get("/api/v1/model/current")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "success"
    assert isinstance(body.get("data", {}).get("model_name"), str)
    assert body["data"]["model_name"]


def test_model_current_endpoint_disables_cache():
    client = TestClient(app)
    resp = client.get("/api/v1/model/current")
    cache_control = resp.headers.get("cache-control", "")
    assert "no-store" in cache_control
