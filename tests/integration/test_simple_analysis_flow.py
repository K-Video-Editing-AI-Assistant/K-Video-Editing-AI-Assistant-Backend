"""Verify that the new analyzer is called by the common workflow."""

from video_assistant.bootstrap import create_application
from video_assistant.core.config import Settings
from video_assistant.core.models import JobState
from tests.conftest import DEMO, finish


def test_simple_analyzer_connected_to_workflow(tmp_path):
    app = create_application(Settings(runtime_dir=tmp_path, analyzer_backend="simple"))
    try:
        with DEMO.open("rb") as handle:
            video = app.ingest("demo.mp4", handle)
        job = finish(app, app.submit_prepare(video.id))
        assert job.state == JobState.SUCCEEDED, job.error_message

        transcript = app.get_transcript(video.id)
        analysis = app.get_analysis(video.id)

        assert analysis.transcript_id == transcript.id
        assert analysis.video_id == video.id
        assert analysis.analyzer_version == "simple-ai-analyzer-v1"
        assert analysis.is_stub is False
        assert len(analysis.topics) == 2
        assert all(topic.segment_ids[0] in {s.id for s in transcript.segments} for topic in analysis.topics)
    finally:
        app.scheduler.shutdown()
