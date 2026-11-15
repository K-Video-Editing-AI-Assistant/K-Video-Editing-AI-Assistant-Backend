"""AI가 생성한 Core 결과를 Figma #24의 조회 API 응답 형식으로 변환합니다.

HTTP 라우팅, 작업 상태 관리, 프로젝트/영상 조회는 Application 담당입니다.
여기서는 AI 결과의 타입과 참조 관계만 검증하여 공개 응답 DTO로 변환합니다.
"""

from pydantic import BaseModel, ConfigDict, Field

from core.errors import AppError, ErrorCode
from core.models import (
    KeywordSuggestion, ProjectAnalysis, RecommendationClip, RecommendationResult,
    RecommendedTopic, SearchRequest, TopicSection, VideoAnalysis,
)


class AnalysisResponse(BaseModel):
    """GET /api/videos/{videoId}/analysis의 AI 관련 응답 필드."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    video_id: str
    video_analysis_id: str
    project_analysis_id: str
    summary: str
    topics: tuple[TopicSection, ...]
    suggested_keywords: tuple[KeywordSuggestion, ...]
    analyzer_version: str
    is_stub: bool


class RecommendationResponse(BaseModel):
    """GET /api/videos/{videoId}/recommendations/{recommendationId} 응답 필드."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation_id: str
    video_id: str
    request_id: str
    project_analysis_id: str
    suggested_title: str
    total_duration_ms: int = Field(ge=0, strict=True)
    clips: tuple[RecommendationClip, ...]
    topics: tuple[RecommendedTopic, ...]
    recommender_version: str
    is_stub: bool


def build_analysis_response(
    video_id: str, analysis: VideoAnalysis, project_analysis: ProjectAnalysis,
) -> AnalysisResponse:
    """영상별 요약과 프로젝트 키워드를 안전하게 합쳐 반환합니다.

    프로젝트의 다른 영상에만 해당하는 키워드는 노출하지 않습니다.
    """
    if not isinstance(analysis, VideoAnalysis) or not isinstance(project_analysis, ProjectAnalysis):
        raise AppError(ErrorCode.INVALID_INPUT, "영상 및 프로젝트 분석 결과가 필요합니다.")
    if not isinstance(video_id, str) or analysis.video_id != video_id:
        raise AppError(ErrorCode.INVALID_REFERENCE, "요청 영상과 분석 결과가 일치하지 않습니다.")
    if analysis.id not in project_analysis.video_analysis_ids:
        raise AppError(ErrorCode.INVALID_REFERENCE, "프로젝트 분석에 해당 영상 결과가 없습니다.")

    topic_ids = {topic.id for topic in analysis.topics}
    keywords = []
    for keyword in project_analysis.suggested_keywords:
        matching = tuple(topic_id for topic_id in keyword.topic_ids if topic_id in topic_ids)
        if matching:
            keywords.append(keyword.model_copy(update={"topic_ids": matching}))

    return AnalysisResponse(
        video_id=video_id, video_analysis_id=analysis.id,
        project_analysis_id=project_analysis.id, summary=analysis.summary,
        topics=analysis.topics, suggested_keywords=tuple(keywords),
        analyzer_version=analysis.analyzer_version, is_stub=analysis.is_stub,
    )


def build_recommendation_response(
    video_id: str, request: SearchRequest, result: RecommendationResult,
) -> RecommendationResponse:
    """원본 요청과 결과의 참조를 함께 확인한 뒤 응답으로 변환합니다.

    빈 추천 결과에는 클립이 없으므로 요청 ID를 별도로 검증해야 합니다.
    """
    if not isinstance(request, SearchRequest) or not isinstance(result, RecommendationResult):
        raise AppError(ErrorCode.INVALID_INPUT, "SearchRequest와 RecommendationResult가 필요합니다.")
    if not isinstance(video_id, str) or not video_id:
        raise AppError(ErrorCode.INVALID_INPUT, "영상 ID가 필요합니다.")
    if (request.video_ids != (video_id,) or request.project_id != result.project_id
            or request.id != result.request_id):
        raise AppError(ErrorCode.INVALID_REFERENCE, "추천 요청과 결과의 영상 또는 프로젝트 ID가 다릅니다.")

    if any(clip.video_id != video_id for clip in result.clips):
        raise AppError(ErrorCode.INVALID_REFERENCE, "추천 결과에 다른 영상의 클립이 포함되어 있습니다.")

    clip_ids = {clip.id for clip in result.clips}
    for topic in result.topics:
        if not set(topic.clip_ids).issubset(clip_ids):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 주제가 존재하지 않는 클립을 참조합니다.")

    duration = sum(clip.end_ms - clip.start_ms for clip in result.clips)
    return RecommendationResponse(
        recommendation_id=result.id, video_id=video_id,
        request_id=result.request_id, project_analysis_id=result.project_analysis_id,
        suggested_title=result.suggested_title, total_duration_ms=duration,
        clips=result.clips, topics=result.topics,
        recommender_version=result.recommender_version, is_stub=result.is_stub,
    )
