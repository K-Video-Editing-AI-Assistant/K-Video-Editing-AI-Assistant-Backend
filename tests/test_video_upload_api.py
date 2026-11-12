from threading import Event

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings
from application.storage import ProjectStore
from core.errors import AppError, ErrorCode
from core.models import JobState
from processing import files


@pytest.fixture
def upload_client(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "probe_video", lambda path: (10000, True))
    app = create_app(Settings(runtime_dir=tmp_path))
    with TestClient(app) as client:
        yield client, app.state.application_service


def upload(client, filename="sample.mp4", content=b"video"):
    return client.post("/api/videos", files={"file": (filename, content, "video/mp4")})


def test_upload_runs_existing_pipeline_and_persists_lookup(upload_client, tmp_path):
    client, service = upload_client
    response = upload(client)
    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True and body["error"] is None
    assert set(body["data"]) == {"videoId", "jobId"}
    video_id, job_id = body["data"]["videoId"], body["data"]["jobId"]
    service.scheduler.futures[job_id].result(timeout=5)
    video = ProjectStore(tmp_path).video_by_id(video_id)
    assert video == service.get_video_by_id(video_id)
    assert video.source_path.read_bytes() == b"video"
    assert service.get_project(video.project_id).video_ids == (video_id,)
    job = service.get_job(job_id)
    assert job.state == JobState.SUCCEEDED and job.stage == "completed"
    assert job.video_id == video_id and job.project_id == video.project_id
    for name in ("transcript", "processed", "analysis"):
        assert service.store.video_data(video.project_id, video_id, name)
    assert (video.source_path.parent / "transcript.srt").is_file()


def test_response_does_not_wait_for_ai_and_failure_is_recorded(upload_client, monkeypatch):
    client, service = upload_client
    started, release = Event(), Event()

    def failing_pipeline(*args):
        started.set()
        assert release.wait(timeout=5)
        raise AppError(ErrorCode.ANALYSIS_FAILED, "provider unavailable")

    monkeypatch.setattr(service, "prepare_video", failing_pipeline)
    try:
        response = upload(client)
        assert response.status_code == 202
        assert started.wait(timeout=2)
        job_id = response.json()["data"]["jobId"]
        assert not service.scheduler.futures[job_id].done()
    finally:
        release.set()
    service.scheduler.futures[job_id].result(timeout=5)
    assert service.get_job(job_id).state == JobState.FAILED
    assert service.get_job(job_id).error_message == "provider unavailable"
    assert service.get_video_by_id(response.json()["data"]["videoId"]).source_path.exists()


@pytest.mark.parametrize("filename,content,status,code", [
    ("sample.txt", b"text", 415, "unsupported_file_type"),
    ("../sample.mp4", b"video", 400, "invalid_input"),
    ("sample.mp4", b"", 400, "invalid_input"),
    ("sample.mp4", b"x" * 11, 413, "upload_too_large"),
])
def test_invalid_upload(upload_client, monkeypatch, filename, content, status, code):
    client, service = upload_client
    monkeypatch.setattr(files, "MAX_UPLOAD_SIZE", 10)
    response = upload(client, filename, content)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["data"] is None
    assert not list(service.store.root.iterdir())


def test_missing_and_multiple_files_are_rejected(upload_client):
    client, _ = upload_client
    for kwargs in ({}, {"json": {"file": "x"}}, {"files": [
        ("file", ("a.mp4", b"a")), ("file", ("b.mp4", b"b")),
    ]}, {"content": b"bad multipart", "headers": {"Content-Type": "multipart/form-data"}}):
        response = client.post("/api/videos", **kwargs)
        assert response.status_code == 400
        assert response.json()["success"] is False


@pytest.mark.parametrize("failure", ["probe", "metadata", "submission"])
def test_failed_acceptance_cleans_up(upload_client, monkeypatch, failure):
    client, service = upload_client

    def fail(*args):
        if failure == "probe":
            raise AppError(ErrorCode.INVALID_INPUT, "invalid video")
        raise OSError("disk unavailable")

    if failure == "probe":
        monkeypatch.setattr(files, "probe_video", fail)
    elif failure == "metadata":
        monkeypatch.setattr(service.store, "save_video", fail)
    else:
        service.scheduler.shutdown()
    response = upload(client)
    assert response.status_code == (400 if failure == "probe" else 500)
    assert not list(service.store.root.iterdir())
    assert not list((service.store.root.parent / "videos").glob("*.json"))
    for path in service.scheduler.store.root.glob("*.json"):
        assert service.get_job(path.stem).state == JobState.FAILED
