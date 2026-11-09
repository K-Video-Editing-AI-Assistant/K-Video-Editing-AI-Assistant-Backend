import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings
from core.errors import AppError, ErrorCode


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


def test_request_validation_error_response(tmp_path):
    app = create_app(Settings(runtime_dir=tmp_path))

    @app.get("/test/validation")
    def validation(count: int):
        return {"count": count}

    with TestClient(app) as client:
        response = client.get("/test/validation", params={"count": "invalid"})

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {"code": "invalid_input", "message": "요청 값이 올바르지 않습니다."},
    }


@pytest.mark.parametrize(
    ("code", "expected_status", "expected_message"),
    [
        (ErrorCode.INVALID_PLAN, 400, "테스트 오류"),
        (ErrorCode.NOT_FOUND, 404, "테스트 오류"),
        (ErrorCode.PLAN_CONFLICT, 409, "테스트 오류"),
        (ErrorCode.RENDER_FAILED, 500, "요청을 처리하는 중 서버 오류가 발생했습니다."),
    ],
)
def test_app_error_response(tmp_path, code, expected_status, expected_message):
    app = create_app(Settings(runtime_dir=tmp_path))

    @app.get("/test/application-error")
    def application_error():
        raise AppError(code, "테스트 오류")

    with TestClient(app) as client:
        response = client.get("/test/application-error")

    assert response.status_code == expected_status
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {"code": code.value, "message": expected_message},
    }
