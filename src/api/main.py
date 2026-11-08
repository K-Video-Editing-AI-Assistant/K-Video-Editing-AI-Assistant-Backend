"""FastAPI entry point; business workflows remain in ApplicationService."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from application.config import Settings
from api.projects import router as projects_router
from bootstrap import create_application
from core.errors import AppError, ErrorCode


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service = create_application(settings)
        app.state.application_service = service
        try:
            yield
        finally:
            service.scheduler.shutdown()
            del app.state.application_service

    app = FastAPI(title="AI 영상편집 어시스턴트 API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Location"],
    )
    app.include_router(projects_router)

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        status_code = {
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.INVALID_INPUT: 400,
        }.get(exc.code, 500)
        return JSONResponse(status_code=status_code, content={
            "error": {
                "code": exc.code.value,
                "message": exc.message if status_code < 500 else "서버 처리 중 오류가 발생했습니다.",
                "retryable": exc.retryable,
            },
        })

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse()

    return app
