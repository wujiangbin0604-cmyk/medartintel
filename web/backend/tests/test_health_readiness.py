from fastapi.testclient import TestClient
from web.backend.app import app


def test_health_is_unavailable_when_not_all_six_models_are_loaded(service, monkeypatch):
    monkeypatch.setattr(service.models, "status", lambda: {"models": [{"loaded": True}, {"loaded": False}]})
    response = TestClient(app).get("/api/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["models_loaded"] == 1


def test_health_is_ready_with_all_six_real_models(service):
    assert service.models.load_all()["all_loaded"]
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["models_loaded"] == response.json()["models_total"] == 6
