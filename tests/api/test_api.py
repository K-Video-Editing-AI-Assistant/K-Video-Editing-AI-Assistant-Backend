from fastapi.testclient import TestClient
from video_assistant.api.app import create_api


def test_health_only_api():
    with TestClient(create_api(cors_origins=[])) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/docs").status_code == 200
        assert set(client.get("/openapi.json").json()["paths"]) == {"/health"}
        assert client.post("/api/v1/videos").status_code == 404
