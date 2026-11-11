"""Single-video intake; AI work runs on the existing application worker."""

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
