from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings
from core.models import Project, Transcript, TranscriptSegment, VideoAsset, new_id


@pytest.fixture
def transcript_client(tmp_path):
    app = create_app(Settings(runtime_dir=tmp_path))
    with TestClient(app) as client:
        service = app.state.application_service
        project_id, video_id = new_id(), new_id()
        video = VideoAsset(
            id=video_id, project_id=project_id, filename="sample.mp4",
            source_path=service.store.video_dir(project_id, video_id) / "source.mp4",
            duration_ms=20000, sha256="0" * 64, has_audio=True,
        )
        service.store.save_project(Project(id=project_id, title="test", video_ids=(video_id,)))
        service.store.save_video(video)
        video.source_path.touch()
        for component, method in (
            (service.transcriber, "transcribe"),
            (service.preprocessor, "preprocess"),
            (service.analyzer, "analyze"),
        ):
            setattr(component, method, Mock(side_effect=AssertionError("조회 중 처리 실행")))
        yield client, service, video
        service.transcriber.transcribe.assert_not_called()
        service.preprocessor.preprocess.assert_not_called()
        service.analyzer.analyze.assert_not_called()


def save_transcript(service, video, segments=()):
    service.store.save_video_data(video.project_id, video.id, "transcript", Transcript(
        id=new_id(), video_id=video.id, transcriber_version="saved-version", segments=segments,
    ))


def test_get_transcript_converts_milliseconds_and_preserves_order(transcript_client):
    client, service, video = transcript_client
    save_transcript(service, video, (
        TranscriptSegment(id=new_id(), start_ms=1, end_ms=1001, text="첫 문장"),
        TranscriptSegment(id=new_id(), start_ms=12000, end_ms=18500, text="두 번째 문장"),
    ))
    response = client.get(f"/api/videos/{video.id}/transcript")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"segments": [
            {"startSeconds": 0.001, "endSeconds": 1.001, "text": "첫 문장"},
            {"startSeconds": 12.0, "endSeconds": 18.5, "text": "두 번째 문장"},
        ]},
        "error": None,
    }


def test_empty_saved_transcript_is_success(transcript_client):
    client, service, video = transcript_client
    save_transcript(service, video)
    response = client.get(f"/api/videos/{video.id}/transcript")
    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"segments": []}, "error": None}


@pytest.mark.parametrize("target,status,code", [
    ("invalid", 400, "invalid_input"),
    ("missing-video", 404, "not_found"),
    ("pending-transcript", 404, "not_found"),
])
def test_get_transcript_errors_use_common_response(transcript_client, target, status, code):
    client, _, video = transcript_client
    video_id = video.id if target == "pending-transcript" else new_id() if target == "missing-video" else target
    response = client.get(f"/api/videos/{video_id}/transcript")
    assert response.status_code == status
    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == code
    assert body["error"]["message"]


def test_get_transcript_openapi_contract(transcript_client):
    client, _, _ = transcript_client
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/videos/{videoId}/transcript"]["get"]
    assert {"200", "400", "404", "500"} <= set(operation["responses"])
    assert operation["parameters"][0]["name"] == "videoId"
    properties = schema["components"]["schemas"]["TranscriptSegmentResponse"]["properties"]
    assert set(properties) == {"startSeconds", "endSeconds", "text"}
