"""API development entry point; feature routers can be added later."""
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_api(cors_origins: list[str] | None = None) -> FastAPI:
    if cors_origins is None:
        load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
        cors_origins = [s.strip() for s in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",") if s.strip()]
    app = FastAPI(title="VideoAssistant API", version="0.1.0",
                  description="API 개발 기본 서버. 현재 상태 확인 API만 제공합니다.")
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins,
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])

    @app.get("/health", tags=["서버 상태"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_api()
