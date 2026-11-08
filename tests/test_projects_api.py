import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings


def test_create_and_get_project_after_restart(tmp_path):
    settings = Settings(runtime_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/projects", json={"title": "  첫 편집  "})
        assert response.status_code == 201
        project = response.json()
        assert project["title"] == "첫 편집"
        assert project["video_ids"] == []
        location = response.headers["location"]
        assert location == f'/api/v1/projects/{project["id"]}'
        assert client.get(location).json() == project
    # A new API/service instance must read the saved project, not an in-memory copy.
    with TestClient(create_app(settings)) as client:
        response = client.get(location)
        assert response.status_code == 200
        assert response.json() == project


@pytest.mark.parametrize("body", [
    {}, {"title": ""}, {"title": "   "}, {"title": 123},
    {"title": None}, {"title": "제목", "id": "client-supplied"},
])
def test_invalid_project_does_not_write_files(tmp_path, body):
    with TestClient(create_app(Settings(runtime_dir=tmp_path))) as client:
        assert client.post("/api/v1/projects", json=body).status_code == 422
        assert list((tmp_path / "projects").iterdir()) == []


def test_missing_project_and_invalid_id(tmp_path):
    with TestClient(create_app(Settings(runtime_dir=tmp_path))) as client:
        response = client.get("/api/v1/projects/" + "a" * 32)
        assert response.status_code == 404
        assert response.json() == {"error": {
            "code": "not_found",
            "message": "저장된 데이터를 찾을 수 없습니다: project.json",
            "retryable": False,
        }}
        assert client.get("/api/v1/projects/invalid-id").status_code == 422


def test_project_response_and_error_are_readable_from_react(tmp_path):
    with TestClient(create_app(Settings(runtime_dir=tmp_path))) as client:
        headers = {"Origin": "http://localhost:5173"}
        response = client.post("/api/v1/projects", json={"title": "제목"}, headers=headers)
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
        assert "Location" in response.headers["access-control-expose-headers"]
        response = client.get("/api/v1/projects/" + "b" * 32, headers=headers)
        assert response.status_code == 404
        assert response.headers["access-control-allow-origin"] == headers["Origin"]
