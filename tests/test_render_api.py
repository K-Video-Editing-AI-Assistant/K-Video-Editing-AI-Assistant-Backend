from threading import Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings
from core.models import (
    Project, VideoAsset, SearchRequest, RecommendationResult, RenderResult,
    Transcript, new_id,
)


@pytest.fixture
def render_client(tmp_path):
    app = create_app(Settings(runtime_dir=tmp_path))
    with TestClient(app) as client:
        service = app.state.application_service
        project_id, video_id = new_id(), new_id()
        service.store.save_project(Project(id=project_id, title="test", video_ids=(video_id,)))
        video = VideoAsset(id=video_id, project_id=project_id, filename="sample.mp4",
                           source_path=service.store.video_dir(project_id, video_id) / "source.mp4",
                           duration_ms=10000, sha256="0" * 64, has_audio=False)
        service.store.save_video(video)
        video.source_path.write_bytes(b"source")
        service.store.save_video_data(project_id, video_id, "transcript", Transcript(
            id=new_id(), video_id=video_id, transcriber_version="test"))
        search = SearchRequest(id=new_id(), project_id=project_id, video_ids=(video_id,), query="test")
        recommendation = RecommendationResult(id=new_id(), project_id=project_id,
                                              request_id=search.id, project_analysis_id=new_id(),
                                              recommender_version="test")
        service.store.save_recommendation(search, recommendation)
        captured = []

        def render(videos, transcripts, plan, destination):
            captured.append((plan, transcripts))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"rendered-video-content")
            return RenderResult(id=new_id(), project_id=project_id, plan_id=plan.id,
                                plan_version=plan.version, output_path=destination,
                                duration_ms=sum(c.end_ms-c.start_ms for c in plan.clips),
                                used_clip_ids=tuple(c.id for c in plan.clips), renderer_version="test")

        service.editor = Mock(VERSION="test", render=Mock(side_effect=render))
        body = {"recommendationId": recommendation.id,
                "clips": [{"startSeconds": 4, "endSeconds": 6}, {"startSeconds": 1, "endSeconds": 2}],
                "subtitles": [{"startSeconds": 0, "endSeconds": 2.5, "text": "최종 자막"}]}
        yield client, service, video, body, captured


def complete(client, service, video, body):
    response = client.post(f"/api/videos/{video.id}/renders", json=body)
    assert response.status_code == 202, response.text
    job_id = response.json()["data"]["jobId"]
    service.scheduler.futures[job_id].result(timeout=5)
    job = client.get(f"/api/jobs/{job_id}").json()["data"]
    assert job["state"] == "succeeded"
    assert job["kind"] == "render" and job["videoId"] == video.id
    return job["resultRef"]


def test_final_edits_result_media_and_range(render_client):
    client, service, video, body, captured = render_client
    render_id = complete(client, service, video, body)
    response = client.get(f"/api/videos/{video.id}/renders/{render_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["durationSeconds"] == 3
    assert "output_path" not in response.text
    plan, transcripts = captured[0]
    assert [(c.start_ms, c.end_ms) for c in plan.clips] == [(4000, 6000), (1000, 2000)]
    assert plan.subtitles[0].end_ms == 2500 and transcripts == ()
    file_response = client.get(data["fileUrl"])
    assert file_response.content == b"rendered-video-content"
    assert file_response.headers["content-type"] == "video/mp4"
    assert file_response.headers["content-disposition"].startswith("inline")
    assert client.get(data["fileUrl"] + "?download=true").headers["content-disposition"].startswith("attachment")
    partial = client.get(data["fileUrl"], headers={"Range": "bytes=0-3"})
    assert partial.status_code == 206 and partial.content == b"rend"


@pytest.mark.parametrize("subtitles,has_transcript", [(None, True), ([], False)])
def test_original_or_disabled_subtitles(render_client, subtitles, has_transcript):
    client, service, video, body, captured = render_client
    complete(client, service, video, {**body, "subtitles": subtitles})
    assert bool(captured[0][1]) is has_transcript
    assert captured[0][0].subtitles == (None if subtitles is None else ())


@pytest.mark.parametrize("update,status", [
    ({"clips": []}, 422),
    ({"clips": [{"startSeconds": 2, "endSeconds": 1}]}, 422),
    ({"clips": [{"startSeconds": 0, "endSeconds": 11}]}, 400),
    ({"subtitles": [{"startSeconds": 0, "endSeconds": 4, "text": "초과"}]}, 400),
    ({"recommendationId": "invalid"}, 400),
])
def test_invalid_final_edits_not_enqueued(render_client, update, status):
    client, service, video, body, _ = render_client
    response = client.post(f"/api/videos/{video.id}/renders", json={**body, **update})
    assert response.status_code == status
    assert response.json()["success"] is False
    assert not service.scheduler.futures


def test_repeated_requests_keep_independent_plans_and_results(render_client):
    client, service, video, body, captured = render_client
    reached, release = Event(), Event()
    original = service.editor.render.side_effect

    def delayed(*args):
        reached.set()
        assert release.wait(5)
        return original(*args)

    service.editor.render.side_effect = delayed
    try:
        first = client.post(f"/api/videos/{video.id}/renders", json=body).json()["data"]["jobId"]
        assert reached.wait(5)
        second = client.post(f"/api/videos/{video.id}/renders", json={
            **body, "clips": [{"startSeconds": 0, "endSeconds": 8}], "subtitles": [],
        }).json()["data"]["jobId"]
        release.set()
        for job_id in (first, second):
            service.scheduler.futures[job_id].result(timeout=5)
            job = service.get_job(job_id)
            assert job.state.value == "succeeded"
            assert client.get(f"/api/videos/{video.id}/renders/{job.result_ref}").status_code == 200
        assert captured[0][0].id != captured[1][0].id
        assert [len(plan.clips) for plan, _ in captured] == [2, 1]
    finally:
        release.set()


def test_failed_generation_and_missing_file(render_client):
    client, service, video, body, _ = render_client
    render_id = complete(client, service, video, body)
    service.get_video_render(video.id, render_id).output_path.unlink()
    assert client.get(f"/api/videos/{video.id}/renders/{render_id}/file").status_code == 404
    service.editor.render.side_effect = RuntimeError("private details")
    response = client.post(f"/api/videos/{video.id}/renders", json=body)
    job_id = response.json()["data"]["jobId"]
    service.scheduler.futures[job_id].result(timeout=5)
    status = client.get(f"/api/jobs/{job_id}")
    assert status.json()["data"]["state"] == "failed"
    assert "private details" not in status.text
