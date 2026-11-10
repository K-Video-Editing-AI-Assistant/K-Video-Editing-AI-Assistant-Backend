"""Figma #24 추천 요청을 기존 Core의 AI 모듈 계약에 연결하는 어댑터.

이 모듈은 HTTP 라우터가 아닙니다. Application 담당자가 URL, Job, 저장소를
처리하고 이 함수로 요청 데이터와 AI 추천 기능을 연결하도록 설계했습니다.
Core의 SearchRequest / RecommendationResult 모델이나 ABC는 변경하지 않습니다.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.errors import AppError, ErrorCode
from core.interfaces import SegmentRecommender
from core.models import (
    EditMode, Project, ProjectAnalysis, RecommendationResult,
    SearchRequest, Transcript, VideoAnalysis, new_id,
)


class SceneRecommendationInput(BaseModel):
    """POST /api/videos/{videoId}/recommendations의 요청 JSON (AI 쪽 계약)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str | None = None
    topic_id: str | None = None
    max_duration_ms: int | None = Field(default=None, gt=0, strict=True)
    max_clips: int = Field(default=5, ge=1, le=20, strict=True)
    edit_mode: EditMode = EditMode.PRESERVE_ORDER

    @model_validator(mode="after")
    def validate_selection(self) -> "SceneRecommendationInput":
        if self.query is not None and not self.query.strip():
            raise ValueError("query는 공백만 입력할 수 없습니다.")
        if self.query is None and self.topic_id is None:
            raise ValueError("query 또는 topic_id 중 하나는 반드시 필요합니다.")
        if self.topic_id is not None and not self.topic_id.strip():
            raise ValueError("topic_id는 공백만 입력할 수 없습니다.")
        return self



@dataclass(frozen=True)
class SceneRecommendationOutcome:
    """Application 저장소가 요청·결과를 함께 기록할 수 있는 반환 계약."""

    request: SearchRequest
    result: RecommendationResult

def _validate_references(
    project: Project, video_id: str, transcript: Transcript,
    analysis: VideoAnalysis, project_analysis: ProjectAnalysis,
) -> None:
    """프로젝트 소속과 자막·분석 연결 관계를 점검합니다."""
    if not isinstance(project, Project) or not isinstance(video_id, str) or not video_id:
        raise AppError(ErrorCode.INVALID_INPUT, "프로젝트 또는 영상 ID가 유효하지 않습니다.")
    if not isinstance(transcript, Transcript) or not isinstance(analysis, VideoAnalysis) or not isinstance(project_analysis, ProjectAnalysis):
        raise AppError(ErrorCode.INVALID_INPUT, "자막 또는 분석 입력 객체가 올바르지 않습니다.")
    if video_id not in project.video_ids or transcript.video_id != video_id or analysis.video_id != video_id:
        raise AppError(ErrorCode.INVALID_REFERENCE, "대상 영상과 프로젝트의 참조 관계가 일치하지 않습니다.")
    if analysis.transcript_id != transcript.id or project_analysis.project_id != project.id:
        raise AppError(ErrorCode.INVALID_REFERENCE, "자막 또는 프로젝트 분석 참조가 일치하지 않습니다.")
    if analysis.id not in project_analysis.video_analysis_ids:
        raise AppError(ErrorCode.INVALID_REFERENCE, "프로젝트 분석에 해당 영상 분석 결과가 포함되지 않았습니다.")


def _limit_total_duration(result: RecommendationResult, max_duration_ms: int | None) -> RecommendationResult:
    """추천 순서를 유지하면서, 전체 길이가 한도를 넘지 않도록 클립 단위로 선택합니다.

    원본 발언을 중간에서 자르지 않습니다. 한도를 넘는 클립은 건너뛰고
    뒤에서 들어갈 수 있는 클립을 찾습니다. 허용 가능한 클립이 없으면 빈 결과입니다.
    """
    if max_duration_ms is None:
        return result

    total = 0
    kept = []
    for clip in result.clips:
        duration = clip.end_ms - clip.start_ms
        if total + duration <= max_duration_ms:
            kept.append(clip)
            total += duration

    if len(kept) == len(result.clips):
        return result

    kept_ids = {clip.id for clip in kept}
    topics = []
    for topic in result.topics:
        ids = tuple(clip_id for clip_id in topic.clip_ids if clip_id in kept_ids)
        if ids:
            topics.append(topic.model_copy(update={"clip_ids": ids}))

    return RecommendationResult.model_validate({
        **result.model_dump(),
        "clips": tuple(kept),
        "topics": tuple(topics),
        "suggested_title": result.suggested_title if kept else "",
    })


def recommend_scene(
    recommender: SegmentRecommender, project: Project, video_id: str,
    transcript: Transcript, analysis: VideoAnalysis,
    project_analysis: ProjectAnalysis, options: SceneRecommendationInput,
) -> SceneRecommendationOutcome:
    """선택한 주제 및 목표 길이를 적용해 AI-04 계약대로 추천합니다.

    - HTTP 본문은 SceneRecommendationInput으로 검증합니다.
    - 선택 주제가 있으면 그 주제의 원본 발언만 AI에 전달합니다.
    - 시간 한도는 추천 결과를 받은 뒤 전체 클립 길이에 적용합니다.
    - 실제 JSON 저장, Job 관리, 202 응답 생성은 Application의 책임입니다.
    """
    if not isinstance(recommender, SegmentRecommender):
        raise AppError(ErrorCode.INVALID_INPUT, "SegmentRecommender 구현체가 필요합니다.")
    if not isinstance(options, SceneRecommendationInput):
        raise AppError(ErrorCode.INVALID_INPUT, "SceneRecommendationInput 객체가 필요합니다.")
    _validate_references(project, video_id, transcript, analysis, project_analysis)

    scoped_transcript = transcript
    scoped_analysis = analysis
    title = ""
    if options.topic_id is not None:
        topic = next((item for item in analysis.topics if item.id == options.topic_id), None)
        if topic is None:
            raise AppError(ErrorCode.INVALID_REFERENCE, "선택한 분석 주제를 찾을 수 없습니다.")
        allowed_ids = set(topic.source_segment_ids)
        source_ids = {segment.id for segment in transcript.segments}
        if not allowed_ids.issubset(source_ids):
            raise AppError(ErrorCode.INVALID_REFERENCE, "선택한 주제가 존재하지 않는 원본 자막을 참조합니다.")
        scoped_transcript = Transcript.model_validate({
            **transcript.model_dump(),
            "segments": tuple(segment for segment in transcript.segments if segment.id in allowed_ids),
        })
        scoped_analysis = analysis.model_copy(update={"topics": (topic,)})
        title = topic.title

    query = (options.query or "").strip()
    if title:
        query = f"{title}: {query}" if query else title
    request = SearchRequest(
        id=new_id(), project_id=project.id, video_ids=(video_id,), query=query,
        max_clips=options.max_clips, edit_mode=options.edit_mode,
    )
    result = recommender.recommend(request, (scoped_transcript,), (scoped_analysis,), project_analysis)
    if not isinstance(result, RecommendationResult):
        raise AppError(ErrorCode.RECOMMENDATION_FAILED, "AI 추천 결과의 타입이 올바르지 않습니다.")
    if result.project_id != project.id or result.request_id != request.id or result.project_analysis_id != project_analysis.id:
        raise AppError(ErrorCode.INVALID_REFERENCE, "AI 추천 결과가 요청 또는 프로젝트와 일치하지 않습니다.")

    if len(result.clips) > options.max_clips:
        raise AppError(ErrorCode.RECOMMENDATION_FAILED, "추천 클립 수가 max_clips를 초과했습니다.")
    known_ids = {segment.id for segment in scoped_transcript.segments}
    original_lookup = {segment.id: (index, segment) for index, segment in enumerate(transcript.segments)}
    for clip in result.clips:
        if clip.video_id != video_id or not clip.source_segment_ids or not set(clip.source_segment_ids).issubset(known_ids):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 클립이 요청 범위 밖의 자막을 참조합니다.")
        positions = [original_lookup[segment_id][0] for segment_id in clip.source_segment_ids]
        if positions != list(range(positions[0], positions[0] + len(positions))):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 클립은 원본 영상의 연속 자막을 참조해야 합니다.")
        selected = [original_lookup[segment_id][1] for segment_id in clip.source_segment_ids]
        if clip.start_ms != min(segment.start_ms for segment in selected) or clip.end_ms != max(segment.end_ms for segment in selected):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 클립 시간이 원본 자막의 시간과 일치하지 않습니다.")

    return SceneRecommendationOutcome(
        request=request, result=_limit_total_duration(result, options.max_duration_ms),
    )
