"""Video intake and saved transcript retrieval."""

from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from api.responses import ApiResponse
from core.errors import AppError, ErrorCode
from processing import files

router = APIRouter(tags=["videos"])


class VideoUploadAccepted(BaseModel):
    videoId: str
    jobId: str


class TranscriptSegmentResponse(BaseModel):
    startSeconds: float
    endSeconds: float
    text: str


class TranscriptResponse(BaseModel):
    segments: list[TranscriptSegmentResponse]


@router.get(
    "/api/videos/{videoId}/transcript",
    response_model=ApiResponse[TranscriptResponse],
    responses={code: {"model": ApiResponse[None]} for code in (400, 404, 500)},
    summary="영상 전체 자막 조회",
    description="저장된 원본 자막을 시간순으로 반환합니다. 시간 단위는 초이며, "
                "음성 인식과 AI 처리를 재실행하지 않습니다. 자막이 아직 생성되지 않았으면 404를 반환합니다.",
)
def get_video_transcript(videoId: str, request: Request):
    transcript = request.app.state.application_service.get_transcript_by_video_id(videoId)
    return ApiResponse.ok(TranscriptResponse(segments=[
        TranscriptSegmentResponse(
            startSeconds=segment.start_ms / 1000,
            endSeconds=segment.end_ms / 1000,
            text=segment.text,
        )
        for segment in transcript.segments
    ]))


@router.post(
    "/api/videos", status_code=202,
    response_model=ApiResponse[VideoUploadAccepted],
    responses={code: {"model": ApiResponse[None]} for code in (400, 413, 415, 500)},
    summary="영상 업로드 및 자막·분석 작업 시작",
)
async def upload_video(request: Request, file: UploadFile = File(...)):
    try:
        form = await request.form()
        if len(form.multi_items()) != 1 or form.multi_items()[0][0] != "file":
            raise AppError(ErrorCode.INVALID_INPUT, "file 필드에 영상 한 개만 보내주세요.")
        contents = await file.read(files.MAX_UPLOAD_SIZE + 1)
        service = request.app.state.application_service
        video, job = await run_in_threadpool(service.upload_and_prepare, file.filename or "", contents)
        return ApiResponse.ok(VideoUploadAccepted(videoId=video.id, jobId=job.id))
    finally:
        await file.close()
