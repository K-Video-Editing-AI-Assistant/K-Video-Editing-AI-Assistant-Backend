"""Shared JSON response models for the FastAPI endpoints."""

from typing import Generic, Self, TypeVar

from pydantic import BaseModel


DataT = TypeVar("DataT")


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[DataT]):
    success: bool
    data: DataT | None
    error: ApiError | None

    @classmethod
    def ok(cls, data: DataT) -> Self:
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str) -> Self:
        return cls(success=False, data=None, error=ApiError(code=code, message=message))
