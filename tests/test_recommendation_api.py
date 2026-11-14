from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from ai.config import AIProvider, AISettings
from ai.recommender import LLMSegmentRecommender
from ai.stub import StubPreprocessor, StubContentAnalyzer
from api.main import create_app
from application.config import Settings
from core.models import Project, Transcript, TranscriptSegment, VideoAsset, new_id


@pytest.fixture
def recommendation_client(tmp_path):
    app = create_app(Settings(runtime_dir=tmp_path))
    with TestClient(app) as client:
        service = app.state.application_service
        project_id, video_id = new_id(), new_id()
        service.store.save_project(Project(id=project_id, title="test", video_ids=(video_id,)))
        video = VideoAsset(id=video_id, project_id=project_id, filename="test.mp4",
                           source_path=service.store.video_dir(project_id, video_id) / "source.mp4",
                           duration_ms=30000, sha256="0" * 64, has_audio=True)
        service.store.save_video(video)
        video.source_path.touch()
        transcript = Transcript(id=new_id(), video_id=video_id, transcriber_version="test", segments=(
            TranscriptSegment(id=new_id(), start_ms=1001, end_ms=11001, text="탄소 흡수 원리"),
        ))
        analysis = StubContentAnalyzer().analyze(StubPreprocessor().preprocess(transcript))
        service.store.save_video_data(project_id, video_id, "transcript", transcript)
        service.store.save_video_data(project_id, video_id, "analysis", analysis)
        service.recommender = LLMSegmentRecommender(AISettings(provider=AIProvider.RULE_BASED))
        service.transcriber.transcribe = Mock(side_effect=AssertionError("Whisper 재실행"))
        service.analyzer.analyze = Mock(side_effect=AssertionError("분석 재실행"))
        yield client, service, video
        service.transcriber.transcribe.assert_not_called()
        service.analyzer.analyze.assert_not_called()


@pytest.mark.parametrize("query,count", [("탄소 흡수", 1), ("무관한검색어", 0)])
def test_create_poll_and_get_recommendation(recommendation_client, query, count):
    client, service, video = recommendation_client
    response = client.post(f"/api/videos/{video.id}/recommendations", json={
        "query": query, "targetDurationSeconds": 10,
    })
    assert response.status_code == 202
    job_id = response.json()["data"]["jobId"]
    service.scheduler.futures[job_id].result(timeout=5)
    status = client.get(f"/api/jobs/{job_id}").json()["data"]
    assert status["state"] == "succeeded"
    assert status["kind"] == "recommend" and status["videoId"] == video.id
    service.recommender.recommend = Mock(side_effect=AssertionError("조회 중 재추천"))
    response = client.get(f'/api/videos/{video.id}/recommendations/{status["resultRef"]}')
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["query"] == query and data["targetDurationSeconds"] == 10
    assert len(data["clips"]) == count
    assert data["totalDurationSeconds"] == count * 10
    assert data["isStub"] is False
    if count:
        assert data["clips"][0]["startSeconds"] == 1.001
        assert data["clips"][0]["endSeconds"] == 11.001
    service.recommender.recommend.assert_not_called()


@pytest.mark.parametrize("payload", [
    {}, {"query": " ", "targetDurationSeconds": 60},
    {"query": "탄소", "targetDurationSeconds": 0},
    {"query": "탄소", "targetDurationSeconds": True},
    {"query": "탄소", "targetDurationSeconds": 1.5},
    {"query": "탄소", "targetDurationSeconds": 60, "maxClips": 21},
])
def test_invalid_recommendation_request(recommendation_client, payload):
    client, service, video = recommendation_client
    response = client.post(f"/api/videos/{video.id}/recommendations", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    assert not service.scheduler.futures


def test_analysis_not_ready(recommendation_client):
    client, service, video = recommendation_client
    (service.store.video_dir(video.project_id, video.id) / "analysis.json").unlink()
    response = client.post(f"/api/videos/{video.id}/recommendations", json={
        "query": "탄소", "targetDurationSeconds": 60,
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_ready"
    assert not service.scheduler.futures


@pytest.mark.parametrize("video_id,rec_id,code", [
    ("invalid", "0" * 32, 400), ("0" * 32, "0" * 32, 404),
])
def test_lookup_errors(recommendation_client, video_id, rec_id, code):
    client, _, _ = recommendation_client
    response = client.get(f"/api/videos/{video_id}/recommendations/{rec_id}")
    assert response.status_code == code
    assert response.json()["success"] is False


def test_recommender_failure_is_visible_in_job_status(recommendation_client):
    client, service, video = recommendation_client
    service.recommender.recommend = Mock(side_effect=RuntimeError("private provider detail"))
    response = client.post(f"/api/videos/{video.id}/recommendations", json={
        "query": "탄소", "targetDurationSeconds": 60,
    })
    assert response.status_code == 202
    job_id = response.json()["data"]["jobId"]
    service.scheduler.futures[job_id].result(timeout=5)
    response = client.get(f"/api/jobs/{job_id}")
    assert response.json()["data"]["state"] == "failed"
    assert response.json()["data"]["resultRef"] is None
    assert "private provider detail" not in response.text


def test_empty_result_from_another_video_is_not_exposed(recommendation_client):
    from core.models import SearchRequest, RecommendationResult

    client, service, video = recommendation_client
    other_id = new_id()
    search = SearchRequest(id=new_id(), project_id=video.project_id, video_ids=(other_id,), query="다른 영상")
    result = RecommendationResult(id=new_id(), project_id=video.project_id, request_id=search.id,
                                  project_analysis_id=new_id(), recommender_version="test")
    service.store.save_recommendation(search, result)
    response = client.get(f"/api/videos/{video.id}/recommendations/{result.id}")
    assert response.status_code == 404
