"""Read persisted background job status without starting work."""

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from api.responses import ApiResponse
from core.errors import AppError, ErrorCode
from core.models import JobKind, JobState


router = APIRouter(tags=["jobs"])


class JobStatusResponse(BaseModel):
    jobId: str
    projectId: str
    videoId: str | None
    kind: JobKind
    state: JobState
    stage: str | None
    progress: int = Field(ge=0, le=100)
    resultRef: str | None
    errorMessage: str | None
    createdAt: datetime
    updatedAt: datetime


@router.get(
    "/api/jobs/{jobId}",
    response_model=ApiResponse[JobStatusResponse],
    responses={code: {"model": ApiResponse[None]} for code in (400, 404, 500)},
    summary="작업 상태 조회",
    description="작업을 재실행하지 않고 저장된 상태를 조회합니다. "
                "succeeded 또는 failed이면 폴링을 종료합니다. "
                "작업 자체가 실패해도 조회에 성공하면 HTTP 200을 반환합니다. "
                "현재 진행률은 중간 단계에서 갱신되지 않으며 성공 시 100입니다.",
)
def get_job_status(jobId: str, request: Request):
    try:
        job = request.app.state.application_service.get_job(jobId)
    except (OSError, ValueError) as exc:
        raise AppError(ErrorCode.STORAGE_FAILED, "작업 상태를 읽지 못했습니다.") from exc

    return ApiResponse.ok(JobStatusResponse(
        jobId=job.id,
        projectId=job.project_id,
        videoId=job.video_id,
        kind=job.kind,
        state=job.state,
        stage=job.stage,
        progress=job.progress,
        resultRef=job.result_ref,
        # Worker exceptions can contain local paths or provider request details.
        errorMessage="작업 처리 중 오류가 발생했습니다." if job.state == JobState.FAILED else None,
        createdAt=job.created_at,
        updatedAt=job.updated_at,
    ))
