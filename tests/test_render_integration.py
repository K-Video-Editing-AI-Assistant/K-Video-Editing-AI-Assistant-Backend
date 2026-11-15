"""End-to-end render API checks using a real FFmpeg process."""

import hashlib
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from application.config import Settings
from core.models import Project, VideoAsset, SearchRequest, RecommendationResult, Transcript, new_id
from processing.files import probe_video


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg/FFprobe required",
)


@pytest.fixture
def real_render_client(tmp_path):
    source = tmp_path / "colors.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=160x90:r=30:d=2",
        "-f", "lavfi", "-i", "color=c=green:s=160x90:r=30:d=2",
        "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=30:d=2",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
    ], check=True, capture_output=True)
    app = create_app(Settings(runtime_dir=tmp_path / "runtime", editor_backend="ffmpeg"))
    with TestClient(app) as client:
        service = app.state.application_service
        project_id, video_id = new_id(), new_id()
        service.store.save_project(Project(id=project_id, title="real integration", video_ids=(video_id,)))
        duration, has_audio = probe_video(source)
        destination = service.store.video_dir(project_id, video_id) / "source.mp4"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        video = VideoAsset(id=video_id, project_id=project_id, filename="colors.mp4",
                           source_path=destination, duration_ms=duration,
                           sha256=hashlib.sha256(source.read_bytes()).hexdigest(), has_audio=has_audio)
        service.store.save_video(video)
        service.store.save_video_data(project_id, video_id, "transcript", Transcript(
            id=new_id(), video_id=video_id, transcriber_version="integration", segments=()))
        search = SearchRequest(id=new_id(), project_id=project_id, video_ids=(video_id,), query="test")
        result = RecommendationResult(id=new_id(), project_id=project_id, request_id=search.id,
                                      project_analysis_id=new_id(), recommender_version="integration")
        service.store.save_recommendation(search, result)
        yield client, service, video, result.id


def pixel_at(path, seconds):
    output = subprocess.run([
        "ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(path),
        "-vf", "scale=1:1", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], check=True, capture_output=True).stdout
    assert len(output) == 3
    return tuple(output)


def test_real_render_api_orders_clips_and_serves_playable_mp4(real_render_client, tmp_path):
    client, service, video, recommendation_id = real_render_client
    response = client.post(f"/api/videos/{video.id}/renders", json={
        "recommendationId": recommendation_id,
        "clips": [{"startSeconds": 4, "endSeconds": 6}, {"startSeconds": 0, "endSeconds": 1}],
        "subtitles": [],
    })
    assert response.status_code == 202, response.text
    job_id = response.json()["data"]["jobId"]
    service.scheduler.futures[job_id].result(timeout=30)
    job = client.get(f"/api/jobs/{job_id}").json()["data"]
    assert job["state"] == "succeeded", job
    assert job["progress"] == 100
    result = client.get(f'/api/videos/{video.id}/renders/{job["resultRef"]}')
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["isStub"] is False
    assert abs(data["durationSeconds"] - 3) < 0.2
    media = client.get(data["fileUrl"])
    assert media.status_code == 200 and media.headers["content-type"] == "video/mp4"
    local_copy = tmp_path / "served.mp4"
    local_copy.write_bytes(media.content)
    duration, has_audio = probe_video(local_copy)
    assert abs(duration - 3000) < 200
    assert has_audio  # Source without audio gets a silent AAC stream.
    r, g, b = pixel_at(local_copy, 0.5)
    assert b > 180 and r < 60 and g < 60  # Blue segment is first.
    r, g, b = pixel_at(local_copy, 2.5)
    assert r > 180 and g < 60 and b < 60  # Red segment follows.
    partial = client.get(data["fileUrl"], headers={"Range": "bytes=0-31"})
    assert partial.status_code == 206 and partial.content == media.content[:32]
    saved = client.get(data["fileUrl"] + "?download=true")
    assert saved.content == media.content
    assert saved.headers["content-disposition"].startswith("attachment")
