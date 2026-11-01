"""Fixed input/output samples used when upstream implementations are unfinished.

No Whisper/LLM/FFmpeg execution is needed to create these Pydantic objects.
The source_path points to the repository's tiny demo MP4 for editing tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from video_assistant.core.models import (
    ApprovedEditPlan, ClipSelection, EditPlan, PlanStatus, RecommendationResult,
    RenderResult, SearchRequest, TopicSection, Transcript, TranscriptSegment,
    VideoAnalysis, VideoAsset,
)

DEMO_VIDEO = Path(__file__).resolve().parents[2] / "examples" / "demo.mp4"
FIXTURE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def sample_video() -> VideoAsset:
    return VideoAsset(
        id="fixture-video-001", project_id="fixture-project-001",
        source_path=DEMO_VIDEO, original_name="demo.mp4", duration_ms=8000,
        sha256=sha256(DEMO_VIDEO.read_bytes()).hexdigest(), has_audio=True,
        created_at=FIXTURE_TIME,
    )


def sample_transcript(video: VideoAsset | None = None) -> Transcript:
    video = video or sample_video()
    return Transcript(
        id="fixture-transcript-001", video_id=video.id, language="ko",
        segments=(
            TranscriptSegment(id="fixture-s1", start_ms=0, end_ms=2000, text="오늘은 인공지능을 소개합니다."),
            TranscriptSegment(id="fixture-s2", start_ms=2000, end_ms=5000, text="AI는 반복 업무를 자동화합니다."),
            TranscriptSegment(id="fixture-s3", start_ms=5000, end_ms=8000, text="AI 활용으로 생산성을 높입니다."),
        ),
        transcriber_version="fixture-transcriber-v1", is_stub=True, created_at=FIXTURE_TIME,
    )


def sample_analysis(transcript: Transcript | None = None) -> VideoAnalysis:
    transcript = transcript or sample_transcript()
    matched = transcript.segments[1:] if len(transcript.segments) > 1 else transcript.segments
    topics = (
        TopicSection(
            id="fixture-topic-001", title="자동화와 생산성",
            start_ms=matched[0].start_ms, end_ms=matched[-1].end_ms,
            segment_ids=tuple(segment.id for segment in matched),
        ),
    ) if matched else ()
    return VideoAnalysis(
        id="fixture-analysis-001", video_id=transcript.video_id,
        transcript_id=transcript.id,
        summary="AI 기술과 반복 업무 자동화, 생산성 향상을 설명하는 영상입니다." if topics else "",
        topics=topics, analyzer_version="fixture-analyzer-v1", is_stub=True,
        created_at=FIXTURE_TIME,
    )


def sample_request(video: VideoAsset | None = None) -> SearchRequest:
    video = video or sample_video()
    return SearchRequest(
        id="fixture-request-001", video_id=video.id, query="AI 활용", max_clips=2,
        created_at=FIXTURE_TIME,
    )


def sample_recommendation(
    request: SearchRequest | None = None,
    transcript: Transcript | None = None,
    analysis: VideoAnalysis | None = None,
) -> RecommendationResult:
    transcript = transcript or sample_transcript()
    analysis = analysis or sample_analysis(transcript)
    request = request or SearchRequest(
        id="fixture-request-001", video_id=transcript.video_id,
        query="AI 활용", max_clips=2, created_at=FIXTURE_TIME,
    )
    selected = transcript.segments[1:] if len(transcript.segments) > 1 else transcript.segments
    clips = tuple(
        ClipSelection(
            id=f"fixture-clip-{index:03d}", start_ms=segment.start_ms,
            end_ms=segment.end_ms, reason="AI 사용 사례와 관련된 테스트 추천입니다.",
            source_segment_ids=(segment.id,),
        ) for index, segment in enumerate(selected[:request.max_clips], start=1)
    )
    return RecommendationResult(
        id="fixture-recommendation-001", request_id=request.id,
        video_id=request.video_id, transcript_id=transcript.id, analysis_id=analysis.id,
        clips=clips, recommender_version="fixture-recommender-v1", is_stub=True,
        created_at=FIXTURE_TIME,
    )


def sample_draft(recommendation: RecommendationResult | None = None) -> EditPlan:
    recommendation = recommendation or sample_recommendation()
    return EditPlan(
        id="fixture-plan-001", video_id=recommendation.video_id,
        request_id=recommendation.request_id, recommendation_id=recommendation.id,
        version=1, clips=recommendation.clips, status=PlanStatus.DRAFT,
        created_at=FIXTURE_TIME,
    )


def sample_approved_plan(recommendation: RecommendationResult | None = None) -> ApprovedEditPlan:
    draft = sample_draft(recommendation)
    return ApprovedEditPlan.model_validate({
        **draft.model_dump(), "status": PlanStatus.APPROVED,
        "approved_at": FIXTURE_TIME,
    })


def sample_render_result(output_path: Path, plan: ApprovedEditPlan | None = None) -> RenderResult:
    """Shape-only sample; not a claim that output_path already contains a rendered MP4."""
    plan = plan or sample_approved_plan()
    return RenderResult(
        id="fixture-render-001", video_id=plan.video_id, plan_id=plan.id,
        plan_version=plan.version, output_path=output_path, duration_ms=8000,
        renderer_version="fixture-renderer-v1", is_stub=True,
        created_at=FIXTURE_TIME,
    )
