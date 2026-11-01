from __future__ import annotations

from uuid import uuid4

from video_assistant.bootstrap import create_application
from video_assistant.core.config import Settings
from video_assistant.core.models import JobState, SearchRequest
from video_assistant.recommendation.keyword import KeywordSegmentRecommender
from tests.conftest import DEMO, finish


def test_keyword_matches_stub_transcript_and_preserves_contract(tmp_path):
    app = create_application(Settings(runtime_dir=tmp_path, recommender_backend="keyword"))
    try:
        with DEMO.open("rb") as handle:
            video = app.ingest("demo.mp4", handle)
        assert finish(app, app.submit_prepare(video.id)).state == JobState.SUCCEEDED
        request = SearchRequest(id=uuid4().hex, video_id=video.id, query="AI 활용", max_clips=2)
        status = finish(app, app.submit_recommend(request))
        assert status.state == JobState.SUCCEEDED, status.error_message
        result = app.get_recommendation(status.result_ref)
        transcript = app.get_transcript(video.id)
        assert result.recommender_version == KeywordSegmentRecommender.VERSION
        assert result.request_id == request.id
        assert result.video_id == video.id
        assert result.transcript_id == transcript.id
        assert len(result.clips) == 2
        assert result.is_stub is False
        ids = {segment.id for segment in transcript.segments}
        assert all(set(clip.source_segment_ids) <= ids for clip in result.clips)
    finally:
        app.scheduler.shutdown()


def test_keyword_no_matches_is_valid(tmp_path):
    app = create_application(Settings(runtime_dir=tmp_path, recommender_backend="keyword"))
    try:
        with DEMO.open("rb") as handle:
            video = app.ingest("demo.mp4", handle)
        assert finish(app, app.submit_prepare(video.id)).state == JobState.SUCCEEDED
        request = SearchRequest(id=uuid4().hex, video_id=video.id, query="zebraclock", max_clips=2)
        status = finish(app, app.submit_recommend(request))
        assert status.state == JobState.SUCCEEDED
        assert app.get_recommendation(status.result_ref).clips == ()
    finally:
        app.scheduler.shutdown()


def test_keyword_max_clips_limit(tmp_path):
    app = create_application(Settings(runtime_dir=tmp_path, recommender_backend="keyword"))
    try:
        with DEMO.open("rb") as handle:
            video = app.ingest("demo.mp4", handle)
        assert finish(app, app.submit_prepare(video.id)).state == JobState.SUCCEEDED
        request = SearchRequest(id=uuid4().hex, video_id=video.id, query="AI", max_clips=1)
        status = finish(app, app.submit_recommend(request))
        assert status.state == JobState.SUCCEEDED
        assert len(app.get_recommendation(status.result_ref).clips) == 1
    finally:
        app.scheduler.shutdown()
