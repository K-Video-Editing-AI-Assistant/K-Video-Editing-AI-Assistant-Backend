"""Integration recipe: unfinished modules remain Stub, finished modules swap in."""

from uuid import uuid4

import pytest

from video_assistant.bootstrap import create_application
from video_assistant.core.config import Settings
from video_assistant.core.models import JobState, SearchRequest
from tests.conftest import DEMO, finish


@pytest.mark.parametrize(
    "analyzer_backend,recommender_backend",
    [
        ("stub", "stub"),
        ("simple", "stub"),
        ("stub", "keyword"),
        ("simple", "keyword"),
    ],
)
def test_mix_and_match_adapters(tmp_path, analyzer_backend, recommender_backend):
    app = create_application(Settings(
        runtime_dir=tmp_path,
        analyzer_backend=analyzer_backend,
        recommender_backend=recommender_backend,
        transcriber_backend="stub", editor_backend="stub",
    ))
    try:
        with DEMO.open("rb") as handle:
            video = app.ingest("demo.mp4", handle)
        prepare = finish(app, app.submit_prepare(video.id))
        assert prepare.state == JobState.SUCCEEDED, prepare.error_message
        transcript = app.get_transcript(video.id)
        analysis = app.get_analysis(video.id)
        assert (transcript.video_id, analysis.video_id, analysis.transcript_id) == (
            video.id, video.id, transcript.id,
        )
        request = SearchRequest(id=uuid4().hex, video_id=video.id, query="AI 활용", max_clips=2)
        search = finish(app, app.submit_recommend(request))
        assert search.state == JobState.SUCCEEDED, search.error_message
        result = app.get_recommendation(search.result_ref)
        assert result.analysis_id == analysis.id
        assert len(result.clips) == 2
        plan = app.create_plan(result.id)
        approved = app.approve_plan(plan.id, plan.version)
        render = finish(app, app.submit_render(approved.id, approved.version))
        assert render.state == JobState.SUCCEEDED, render.error_message
        output = app.get_render_result(render.result_ref)
        assert output.output_path.is_file()
        assert output.plan_version == approved.version
        assert output.is_stub  # copied original, not real clipping
    finally:
        app.scheduler.shutdown()


def test_workflow_blocks_wrong_recommendation_reference(service, video):
    finished = finish(service, service.submit_prepare(video.id))
    assert finished.state == JobState.SUCCEEDED
    original = service.recommender.recommend

    def bad_recommendation(request, transcript, analysis):
        good = original(request, transcript, analysis)
        return good.model_copy(update={"analysis_id": "wrong-analysis-id"})

    service.recommender.recommend = bad_recommendation
    req = SearchRequest(id=uuid4().hex, video_id=video.id, query="AI", max_clips=2)
    result = finish(service, service.submit_recommend(req))
    assert result.state == JobState.FAILED
    assert result.error_code == "recommendation_failed"
    assert result.result_ref is None
