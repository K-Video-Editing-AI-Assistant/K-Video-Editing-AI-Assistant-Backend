"""Five-module contract checks, using deterministic upstream fixtures."""

from pathlib import Path

import pytest

from video_assistant.analysis.stub import StubContentAnalyzer
from video_assistant.core.errors import AppError, ErrorCode
from video_assistant.core.interfaces import (
    ContentAnalyzer, SegmentRecommender, Transcriber, VideoEditor,
)
from video_assistant.core.media import probe_mp4
from video_assistant.core.models import (
    ApprovedEditPlan, RecommendationResult, Transcript, VideoAnalysis,
)
from video_assistant.editing.stub import StubVideoEditor
from video_assistant.recommendation.keyword import KeywordSegmentRecommender
from video_assistant.recommendation.stub import StubSegmentRecommender
from video_assistant.transcription.stub import StubTranscriber
from tests.fixtures.contract_samples import (
    sample_analysis, sample_approved_plan, sample_draft,
    sample_recommendation, sample_request, sample_transcript, sample_video,
)


def test_fixed_samples_form_one_consistent_data_chain():
    video = sample_video()
    transcript = sample_transcript(video)
    analysis = sample_analysis(transcript)
    request = sample_request(video)
    result = sample_recommendation(request, transcript, analysis)
    plan = sample_draft(result)
    approved = sample_approved_plan(result)
    assert result.request_id == request.id
    assert result.video_id == transcript.video_id == analysis.video_id == plan.video_id == video.id
    assert analysis.transcript_id == result.transcript_id == transcript.id
    assert result.analysis_id == analysis.id
    assert plan.recommendation_id == result.id
    assert approved.clips == plan.clips and approved.version == plan.version
    assert {segment.id for segment in transcript.segments} >= {
        item for clip in result.clips for item in clip.source_segment_ids
    }


def test_transcriber_stub_respects_input_video_and_output_type():
    video = sample_video()
    transcriber: Transcriber = StubTranscriber()
    output = transcriber.transcribe(video)
    assert isinstance(output, Transcript)
    assert output.video_id == video.id
    assert output.transcriber_version == transcriber.VERSION
    assert output.is_stub is True
    assert all(0 <= segment.start_ms < segment.end_ms <= video.duration_ms for segment in output.segments)


def test_analyzer_stub_accepts_fixture_input_without_running_transcriber():
    upstream = sample_transcript()
    analyzer: ContentAnalyzer = StubContentAnalyzer()
    result = analyzer.analyze(upstream)
    assert isinstance(result, VideoAnalysis)
    assert result.transcript_id == upstream.id
    assert result.video_id == upstream.video_id
    assert result.analyzer_version == analyzer.VERSION
    assert {sid for topic in result.topics for sid in topic.segment_ids} <= {s.id for s in upstream.segments}


@pytest.mark.parametrize("adapter", [StubSegmentRecommender(), KeywordSegmentRecommender()])
def test_recommender_accepts_fixed_upstream_contracts(adapter: SegmentRecommender):
    video = sample_video()
    transcript = sample_transcript(video)
    analysis = sample_analysis(transcript)
    request = sample_request(video)
    result = adapter.recommend(request, transcript, analysis)
    assert isinstance(result, RecommendationResult)
    assert (result.video_id, result.request_id, result.transcript_id, result.analysis_id) == (
        video.id, request.id, transcript.id, analysis.id,
    )
    assert result.recommender_version == adapter.VERSION
    assert len(result.clips) <= request.max_clips
    assert all(clip.source_segment_ids for clip in result.clips)
    known = {seg.id for seg in transcript.segments}
    assert all(
        0 <= clip.start_ms < clip.end_ms <= video.duration_ms
        and set(clip.source_segment_ids) <= known
        for clip in result.clips
    )


def test_editor_stub_accepts_fixed_approved_plan_without_upstream_execution(tmp_path: Path):
    video = sample_video()
    approved: ApprovedEditPlan = sample_approved_plan()
    editor: VideoEditor = StubVideoEditor()
    output_path = tmp_path / "stub_render.mp4"
    result = editor.render(video, approved, output_path)
    assert result.plan_id == approved.id
    assert result.plan_version == approved.version
    assert result.video_id == video.id
    assert result.output_path == output_path
    assert result.is_stub is True
    assert output_path.read_bytes() == video.source_path.read_bytes()  # no actual cuts
    assert abs(probe_mp4(output_path)[0] - result.duration_ms) <= 100


def test_empty_upstream_transcript_is_valid_and_propagates_to_empty_recommendation():
    transcript = sample_transcript().model_copy(update={"segments": ()})
    analysis = StubContentAnalyzer().analyze(transcript)
    result = StubSegmentRecommender().recommend(sample_request(), transcript, analysis)
    assert analysis.topics == ()
    assert result.clips == ()


def test_empty_plan_cannot_be_approved():
    with pytest.raises(ValueError):
        ApprovedEditPlan.model_validate({
            **sample_draft().model_dump(), "clips": [],
            "status": "approved", "approved_at": "2026-01-01T00:00:00Z",
        })


def test_data_contract_roundtrips_as_json():
    result = sample_recommendation()
    assert RecommendationResult.model_validate_json(result.model_dump_json()) == result
