from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings


def test_health_and_service_lifecycle(tmp_path):
    app = create_app(Settings(runtime_dir=tmp_path))
    assert not hasattr(app.state, "application_service")
    with TestClient(app) as client:
        service = app.state.application_service
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert app.state.application_service is service
        assert client.get("/openapi.json").json()["paths"]["/api/v1/health"]
    assert not hasattr(app.state, "application_service")
    assert service.scheduler.worker._shutdown


def test_react_cors_preflight(tmp_path):
    app = create_app(Settings(runtime_dir=tmp_path))
    with TestClient(app) as client:
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = client.options("/api/v1/health", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
        headers["Origin"] = "https://unlisted.example"
        response = client.options("/api/v1/health", headers=headers)
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


def test_cors_env_priority(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:4000, http://localhost:4001")
    assert Settings.from_env().cors_origins == (
        "http://localhost:4000", "http://localhost:4001",
    )
