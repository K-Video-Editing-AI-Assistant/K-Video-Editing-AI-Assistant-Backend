"""Asynchronous single-video recommendations for the segments screen."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.responses import ApiResponse
from core.errors import AppError, ErrorCode

router = APIRouter(tags=["recommendations"])


class RecommendationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000, examples=["탄소 흡수 원리를 설명하는 부분만 모아줘"])
    targetDurationSeconds: int = Field(gt=0, strict=True, examples=[60])
    maxClips: int = Field(default=20, ge=1, le=20, strict=True)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("추천 요청을 입력해주세요.")
        return value


class RecommendationAccepted(BaseModel):
    videoId: str
    jobId: str


class RecommendationClipResponse(BaseModel):
    clipId: str
    startSeconds: float
    endSeconds: float
    reason: str


class RecommendationResponse(BaseModel):
    recommendationId: str
    videoId: str
    query: str
    targetDurationSeconds: float | None
    totalDurationSeconds: float
    suggestedTitle: str
    clips: list[RecommendationClipResponse]
    isStub: bool
    recommenderVersion: str


@router.post(
    "/api/videos/{videoId}/recommendations", status_code=202,
    response_model=ApiResponse[RecommendationAccepted],
    responses={code: {"model": ApiResponse[None]} for code in (400, 404, 409, 422, 500)},
    summary="추천 구간 생성 요청",
    description="분석 완료 후 자연어 요청과 전체 목표 길이(정수 초)를 전달합니다. "
                "jobId로 작업 상태를 조회하고 성공 시 resultRef를 recommendationId로 사용합니다. "
                "추천 구간 합산 길이는 목표의 최대 110%이며, 관련 내용이 부족하면 짧거나 비어 있을 수 있습니다. "
                "실제 영상 파일은 생성하지 않습니다.",
)
def create_recommendation(videoId: str, body: RecommendationInput, request: Request):
    try:
        job = request.app.state.application_service.submit_video_recommendation(
            videoId, body.query, body.targetDurationSeconds * 1000, body.maxClips,
        )
    except (OSError, ValueError) as exc:
        raise AppError(ErrorCode.STORAGE_FAILED, "추천 작업을 접수하지 못했습니다.") from exc
    return ApiResponse.ok(RecommendationAccepted(videoId=videoId, jobId=job.id))


@router.get(
    "/api/videos/{videoId}/recommendations/{recommendationId}",
    response_model=ApiResponse[RecommendationResponse],
    responses={code: {"model": ApiResponse[None]} for code in (400, 404, 500)},
    summary="추천 구간 결과 조회",
    description="성공한 추천 작업의 resultRef로 저장된 결과를 조회합니다. 시간 단위는 초입니다. "
                "빈 clips는 정상적인 빈 추천이며, 조회 시 AI 처리를 재실행하지 않습니다.",
)
def get_recommendation(videoId: str, recommendationId: str, request: Request):
    try:
        search, result = request.app.state.application_service.get_video_recommendation(videoId, recommendationId)
    except (OSError, ValueError) as exc:
        raise AppError(ErrorCode.STORAGE_FAILED, "추천 결과를 읽지 못했습니다.") from exc
    return ApiResponse.ok(RecommendationResponse(
        recommendationId=result.id, videoId=videoId, query=search.query,
        targetDurationSeconds=search.target_duration_ms / 1000 if search.target_duration_ms is not None else None,
        totalDurationSeconds=sum(c.end_ms - c.start_ms for c in result.clips) / 1000,
        suggestedTitle=result.suggested_title, isStub=result.is_stub,
        recommenderVersion=result.recommender_version,
        clips=[RecommendationClipResponse(clipId=c.id, startSeconds=c.start_ms / 1000,
                                          endSeconds=c.end_ms / 1000, reason=c.reason)
               for c in result.clips],
    ))
