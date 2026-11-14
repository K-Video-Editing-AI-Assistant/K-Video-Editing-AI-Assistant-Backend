import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from ai.config import AISettings, AIFallbackPolicy
from ai.providers.gemini import GeminiProcessingError
from ai.recommender import LLMSegmentRecommender, _GeminiRecommendation
from ai.stub import StubPreprocessor, StubContentAnalyzer, StubProjectAnalyzer
from application.config import Settings
from bootstrap import create_application
from core.errors import AppError, ErrorCode
from core.models import Project, SearchRequest, Transcript, TranscriptSegment, VideoAsset, new_id


@pytest.fixture
def recommendation_context(tmp_path):
    app = create_application(Settings(runtime_dir=tmp_path, recommender_backend="llm"))
    project = Project(id=new_id(), title="test", video_ids=(new_id(),))
    video = VideoAsset(id=project.video_ids[0], project_id=project.id, filename="test.mp4",
                       source_path=app.store.video_dir(project.id, project.video_ids[0]) / "source.mp4", duration_ms=90000,
                       sha256="0" * 64, has_audio=True)
    transcript = Transcript(id=new_id(), video_id=video.id, transcriber_version="test", segments=(
        TranscriptSegment(id="first", start_ms=1000, end_ms=21000, text="탄소 흡수 원리"),
        TranscriptSegment(id="second", start_ms=40000, end_ms=65000, text="탄소 흡수 실험"),
    ))
    analysis = StubContentAnalyzer().analyze(StubPreprocessor().preprocess(transcript))
    project_analysis = StubProjectAnalyzer().analyze_project(project, (analysis,))
    app.store.save_project(project)
    app.store.save_video(video)
    video.source_path.touch()
    app.store.save_video_data(project.id, video.id, "transcript", transcript)
    app.store.save_video_data(project.id, video.id, "analysis", analysis)
    app.store.project_analysis = Mock(return_value=project_analysis)
    request = SearchRequest(id=new_id(), project_id=project.id, video_ids=(video.id,),
                            query="탄소 흡수 설명", target_duration_ms=45000)
    try:
        yield app, request
    finally:
        app.close()


def test_gemini_connection_target_prompt_and_saved_result(recommendation_context, monkeypatch):
    app, request = recommendation_context
    app.recommender = LLMSegmentRecommender(AISettings(gemini_model="test-model"), gemini_client=Mock())
    parsed = _GeminiRecommendation(suggested_title="탄소 흡수", clips=[
        {"video_id": request.video_ids[0], "segment_ids": ["first"], "reason": "원리"},
        {"video_id": request.video_ids[0], "segment_ids": ["second"], "reason": "실험"},
    ], groups=[])
    generate = Mock(return_value=parsed)
    monkeypatch.setattr("ai.recommender.GeminiStructuredGenerator.generate", generate)
    app.transcriber.transcribe = Mock(side_effect=AssertionError("Whisper 재실행"))
    result = app.recommend(request)
    payload = json.loads(generate.call_args.args[0].split("입력 JSON:\n")[1])
    assert payload["target_duration_ms"] == 45000
    assert payload["query"] == request.query
    assert [(c.start_ms, c.end_ms) for c in result.clips] == [(1000, 21000), (40000, 65000)]
    assert sum(c.end_ms - c.start_ms for c in result.clips) == 45000
    assert result.recommender_version == "gemini-recommender-v1:test-model"
    assert app.get_recommendation(request.project_id, result.id) == result
    app.transcriber.transcribe.assert_not_called()


def test_rule_based_fallback_is_accepted_by_service(recommendation_context, monkeypatch):
    app, request = recommendation_context
    app.recommender = LLMSegmentRecommender(AISettings(fallback=AIFallbackPolicy.RULE_BASED), gemini_client=Mock())
    monkeypatch.setattr("ai.recommender.GeminiStructuredGenerator.generate",
                        Mock(side_effect=GeminiProcessingError("test")))
    result = app.recommend(request)
    assert result.recommender_version == app.recommender.FALLBACK_VERSION
    assert not result.is_stub


def test_raise_policy_does_not_return_stub(recommendation_context, monkeypatch):
    app, request = recommendation_context
    app.recommender = LLMSegmentRecommender(AISettings(fallback=AIFallbackPolicy.RAISE), gemini_client=Mock())
    monkeypatch.setattr("ai.recommender.GeminiStructuredGenerator.generate",
                        Mock(side_effect=GeminiProcessingError("test")))
    with pytest.raises(AppError) as error:
        app.recommend(request)
    assert error.value.code == ErrorCode.RECOMMENDATION_FAILED


@pytest.mark.parametrize("duration", [0, -1, True, 1.5])
def test_target_duration_must_be_positive_integer(duration):
    with pytest.raises(ValidationError):
        SearchRequest(id="request", project_id="project", video_ids=("video",),
                      query="내용", target_duration_ms=duration)
