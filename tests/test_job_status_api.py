from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings
from application.jobs import JobStore
from core.models import JobKind, JobState, JobStatus, new_id


@pytest.fixture
def job_client(tmp_path, monkeypatch):
    app = create_app(Settings(runtime_dir=tmp_path))
    with TestClient(app) as client:
        service = app.state.application_service
        submit = Mock(side_effect=AssertionError("조회 중 작업 등록"))
        monkeypatch.setattr(service.scheduler, "submit", submit)
        yield client, service.scheduler.store
        submit.assert_not_called()


@pytest.mark.parametrize("kind", list(JobKind))
@pytest.mark.parametrize("state", list(JobState))
def test_saved_job_status_and_public_fields(job_client, kind, state):
    client, store = job_client
    job = JobStatus(
        id=new_id(), project_id=new_id(), video_id=new_id(), kind=kind, state=state,
        stage="completed" if state == JobState.SUCCEEDED else "analyzing" if state != JobState.QUEUED else None,
        progress=100 if state == JobState.SUCCEEDED else 0,
        result_ref=new_id() if state == JobState.SUCCEEDED else None,
        error_message="provider secret /private/source.mp4" if state == JobState.FAILED else None,
    )
    store.save(job)
    path = store.root / f"{job.id}.json"
    original = path.read_bytes()
    for _ in range(2):
        response = client.get(f"/api/jobs/{job.id}")
        assert response.status_code == 200
        assert response.json() == {
            "success": True, "error": None,
            "data": {
                "jobId": job.id, "projectId": job.project_id, "videoId": job.video_id,
                "kind": kind.value, "state": state.value, "stage": job.stage,
                "progress": job.progress, "resultRef": job.result_ref,
                "errorMessage": "작업 처리 중 오류가 발생했습니다." if state == JobState.FAILED else None,
                "createdAt": job.model_dump(mode="json")["created_at"],
                "updatedAt": job.model_dump(mode="json")["updated_at"],
            },
        }
    assert path.read_bytes() == original


def test_project_job_without_video_or_stage(job_client):
    client, store = job_client
    job = JobStatus(id=new_id(), project_id=new_id(), kind=JobKind.RECOMMEND)
    store.save(job)
    data = client.get(f"/api/jobs/{job.id}").json()["data"]
    assert data["videoId"] is None
    assert data["stage"] is None
    assert data["resultRef"] is None
    assert data["errorMessage"] is None


@pytest.mark.parametrize("job_id,status,code", [
    ("invalid", 400, "invalid_input"),
    ("A" * 32, 400, "invalid_input"),
    ("0" * 31, 400, "invalid_input"),
    ("g" * 32, 400, "invalid_input"),
    ("0" * 32, 404, "not_found"),
])
def test_invalid_or_missing_job(job_client, job_id, status, code):
    client, _ = job_client
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == status
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == code
    assert body["error"]["message"]


def test_corrupt_storage_returns_common_server_error(job_client):
    client, store = job_client
    job_id = new_id()
    (store.root / f"{job_id}.json").write_text('{"secret":', encoding="utf-8")
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 500
    assert response.json() == {
        "success": False, "data": None,
        "error": {"code": "storage_failed", "message": "요청을 처리하는 중 서버 오류가 발생했습니다."},
    }


def test_unreadable_storage_returns_common_server_error(job_client, monkeypatch):
    client, store = job_client
    monkeypatch.setattr(store, "load", Mock(side_effect=PermissionError("private path")))
    response = client.get(f"/api/jobs/{new_id()}")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "storage_failed"
    assert "private path" not in response.text


@pytest.mark.parametrize("state", [JobState.QUEUED, JobState.RUNNING])
def test_interrupted_job_is_failed_after_restart(tmp_path, state):
    job = JobStatus(id=new_id(), project_id=new_id(), kind=JobKind.PREPARE, state=state)
    JobStore(tmp_path).save(job)
    app = create_app(Settings(runtime_dir=tmp_path))
    with TestClient(app) as client:
        response = client.get(f"/api/jobs/{job.id}")
        assert response.status_code == 200
        assert response.json()["data"]["state"] == "failed"
        assert response.json()["data"]["errorMessage"]
        assert not app.state.application_service.scheduler.futures


def test_openapi_documents_job_status_contract(job_client):
    client, _ = job_client
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/jobs/{jobId}"]["get"]
    assert {"200", "400", "404", "500"} <= set(operation["responses"])
    assert operation["parameters"][0]["name"] == "jobId"
    assert set(schema["components"]["schemas"]["JobStatusResponse"]["properties"]) == {
        "jobId", "projectId", "videoId", "kind", "state", "stage", "progress",
        "resultRef", "errorMessage", "createdAt", "updatedAt",
    }
