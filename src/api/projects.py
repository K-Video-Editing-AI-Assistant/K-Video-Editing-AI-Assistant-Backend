"""Project creation and lookup through the application service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from api.dependencies import get_application_service
from application.service import ApplicationService
from core.models import Project


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]


router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
Service = Annotated[ApplicationService, Depends(get_application_service)]


@router.post("", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(body: CreateProjectRequest, response: Response, service: Service) -> Project:
    project = service.create_project(body.title)
    response.headers["Location"] = f"/api/v1/projects/{project.id}"
    return project


@router.get("/{project_id}", response_model=Project)
def get_project(
    project_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")], service: Service,
) -> Project:
    return service.get_project(project_id)
