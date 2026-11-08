"""Reuse the service owned by the API application's lifespan."""

from fastapi import Request

from application.service import ApplicationService


def get_application_service(request: Request) -> ApplicationService:
    return request.app.state.application_service
