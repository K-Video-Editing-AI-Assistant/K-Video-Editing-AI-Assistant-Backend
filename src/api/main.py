"""FastAPI entry point; business workflows remain in ApplicationService."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from application.config import Settings


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(settings: Settings | None = None) -> FastAPI:

    app = FastAPI(title="CLIPNOTE API", version="0.1.0")

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse()

    return app
