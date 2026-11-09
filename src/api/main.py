"""FastAPI entry point; business workflows remain in ApplicationService."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.exception_handlers import handle_app_error, handle_request_validation_error
from application.config import Settings
from bootstrap import create_application
from core.errors import AppError


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
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(AppError, handle_app_error)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse()

    return app
