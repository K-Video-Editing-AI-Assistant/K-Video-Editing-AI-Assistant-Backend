"""ASGI entry point for FastAPI Cloud deployment."""

from api.main import create_app

app = create_app()
