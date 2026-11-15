"""Render final frontend edits and expose one media URL for playback or saving."""

from contextlib import contextmanager
from typing import Self

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.responses import ApiResponse
from core.errors import AppError, ErrorCode
from core.models import PlanSubtitle, SubtitleStyle

router = APIRouter(tags=["renders"])


class TimeRangeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    startSeconds: float = Field(ge=0, multiple_of=0.001, allow_inf_nan=False, strict=True)
    endSeconds: float = Field(gt=0, multiple_of=0.001, allow_inf_nan=False, strict=True)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if round(self.endSeconds * 1000) <= round(self.startSeconds * 1000):
            raise ValueError("종료 시각은 시작 시각보다 커야 합니다.")
        return self


class SubtitleInput(TimeRangeInput):
    text: str = Field(min_length=1, max_length=2000)


class RenderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendationId: str
    clips: list[TimeRangeInput] = Field(min_length=1, max_length=100)
    subtitleStyle: SubtitleStyle = SubtitleStyle.BASIC
    subtitles: list[SubtitleInput] | None = Field(default=None, max_length=10000)


class RenderAccepted(BaseModel):
    videoId: str
    jobId: str


class RenderResponse(BaseModel):
    renderId: str
    videoId: str
    durationSeconds: float
    fileUrl: str
    isStub: bool


@contextmanager
def storage_errors():
    try:
        yield
    except (OSError, ValueError) as exc:
        raise AppError(ErrorCode.STORAGE_FAILED, "영상 생성 데이터를 처리하지 못했습니다.") from exc


@router.post(
    "/api/videos/{videoId}/renders", status_code=202,
    response_model=ApiResponse[RenderAccepted],
    responses={code: {"model": ApiResponse[None]} for code in (400, 404, 422, 500)},
    summary="최종 편집 영상 생성",
    description="프론트에서 확정한 clips 배열 순서대로 원본 구간을 합칩니다. 시간은 초이며 소수 셋째 자리까지 지원합니다. "
                "subtitles 시간은 합쳐진 결과 영상 기준입니다. 생략/null은 원본 자막, []는 자막 없이 생성합니다. "
                "jobId로 기존 작업 상태를 조회하고 succeeded의 resultRef를 renderId로 사용합니다. "
                "각 요청은 독립된 편집 내용을 사용합니다.",
)
def create_render(videoId: str, body: RenderInput, request: Request):
    subtitles = None if body.subtitles is None else tuple(
        PlanSubtitle(start_ms=round(s.startSeconds * 1000), end_ms=round(s.endSeconds * 1000), text=s.text)
        for s in body.subtitles
    )
    with storage_errors():
        job = request.app.state.application_service.submit_final_video(
            videoId, body.recommendationId,
            tuple((round(c.startSeconds * 1000), round(c.endSeconds * 1000)) for c in body.clips),
            body.subtitleStyle, subtitles,
        )
    return ApiResponse.ok(RenderAccepted(videoId=videoId, jobId=job.id))


@router.get(
    "/api/videos/{videoId}/renders/{renderId}",
    response_model=ApiResponse[RenderResponse],
    responses={code: {"model": ApiResponse[None]} for code in (400, 404, 500)},
    summary="생성 영상 결과 조회",
    description="완료된 작업의 resultRef로 조회합니다. fileUrl은 API 서버 기준 상대 경로이며 재생과 저장에 사용합니다. "
                "생성 중이거나 파일이 없으면 404입니다. isStub=true이면 실제 편집 영상이 아닌 개발용 결과입니다.",
)
def get_render(videoId: str, renderId: str, request: Request):
    with storage_errors():
        result = request.app.state.application_service.get_video_render(videoId, renderId)
    return ApiResponse.ok(RenderResponse(
        renderId=result.id, videoId=videoId, durationSeconds=result.duration_ms / 1000,
        fileUrl=f"/api/videos/{videoId}/renders/{renderId}/file", isStub=result.is_stub,
    ))


@router.get(
    "/api/videos/{videoId}/renders/{renderId}/file", name="render_file",
    response_class=FileResponse,
    responses={200: {"content": {"video/mp4": {}}},
               **{code: {"model": ApiResponse[None]} for code in (400, 404, 500)}},
    summary="생성 영상 파일 제공",
    description="동일 URL을 영상 재생과 저장에 사용합니다. download=true이면 첨부 파일로 제공합니다. "
                "브라우저의 Range 요청을 지원합니다.",
)
def get_render_file(videoId: str, renderId: str, request: Request, download: bool = False):
    with storage_errors():
        result = request.app.state.application_service.get_video_render(videoId, renderId)
    return FileResponse(
        result.output_path.resolve(), media_type="video/mp4", filename=f"edited-{renderId}.mp4",
        content_disposition_type="attachment" if download else "inline",
    )
