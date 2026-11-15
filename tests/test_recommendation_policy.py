import pytest

from core.errors import AppError
from core.models import (
    SearchRequest, Transcript, TranscriptSegment, RecommendationClip,
    RecommendationResult, RecommendedTopic,
)
from core.recommendations import validate_and_limit_recommendation


@pytest.fixture
def policy_data():
    transcript = Transcript(id="t", video_id="v", transcriber_version="test", segments=(
        TranscriptSegment(id="s1", start_ms=0, end_ms=20000, text="원리"),
        TranscriptSegment(id="s2", start_ms=30000, end_ms=55000, text="실험"),
        TranscriptSegment(id="s3", start_ms=70000, end_ms=85000, text="결론"),
    ))
    clips = tuple(RecommendationClip(id=f"c{i}", video_id="v", start_ms=s.start_ms,
                                     end_ms=s.end_ms, source_segment_ids=(s.id,))
                  for i, s in enumerate(transcript.segments))
    result = RecommendationResult(id="r", project_id="p", request_id="q", project_analysis_id="a",
                                  suggested_title="추천", clips=clips, recommender_version="test",
                                  topics=(RecommendedTopic(id="topic", title="주제", clip_ids=tuple(c.id for c in clips)),))
    return transcript, result


@pytest.mark.parametrize("target,expected", [
    (60000, [20000, 25000, 15000]),
    (55000, [20000, 25000, 15000]),  # 60 seconds fits the 10% allowance.
    (45000, [20000, 25000]),
    (20000, [20000]),
    (10000, []),  # No utterance can fit without being cut.
    (120000, [20000, 25000, 15000]),  # Do not invent content to fill the target.
    (None, [20000, 25000, 15000]),
])
def test_total_duration_policy_and_topic_references(policy_data, target, expected):
    transcript, result = policy_data
    request = SearchRequest(id="q", project_id="p", video_ids=("v",), query="요약", target_duration_ms=target)
    limited = validate_and_limit_recommendation(request, result, (transcript,))
    assert [c.end_ms - c.start_ms for c in limited.clips] == expected
    assert all(cid in {c.id for c in limited.clips} for t in limited.topics for cid in t.clip_ids)
    if not expected:
        assert limited.topics == () and limited.suggested_title == ""


@pytest.mark.parametrize("change", [
    {"start_ms": 1},
    {"source_segment_ids": ("missing",)},
    {"source_segment_ids": ("s1", "s1")},
    {"source_segment_ids": ("s1", "s3"), "end_ms": 85000},
    {"source_segment_ids": ("s2", "s1"), "end_ms": 55000},
])
def test_invalid_source_boundaries_are_rejected_even_when_over_budget(policy_data, change):
    transcript, result = policy_data
    clip = RecommendationClip.model_validate({**result.clips[0].model_dump(), **change})
    result = result.model_copy(update={"clips": (clip,)})
    request = SearchRequest(id="q", project_id="p", video_ids=("v",), query="요약", target_duration_ms=1)
    with pytest.raises(AppError):
        validate_and_limit_recommendation(request, result, (transcript,))


def test_overlapping_clips_rejected(policy_data):
    transcript, result = policy_data
    combined = RecommendationClip(id="combined", video_id="v", start_ms=0, end_ms=55000,
                                  source_segment_ids=("s1", "s2"))
    result = result.model_copy(update={"clips": (combined, result.clips[1])})
    request = SearchRequest(id="q", project_id="p", video_ids=("v",), query="요약")
    with pytest.raises(AppError, match="겹칩니다"):
        validate_and_limit_recommendation(request, result, (transcript,))
