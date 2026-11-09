"""Translate request and application errors into public API responses."""

import logging
from http import HTTPStatus

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.responses import ApiResponse
from core.errors import AppError, ErrorCode


logger = logging.getLogger(__name__)

APP_ERROR_STATUS = {
    ErrorCode.INVALID_INPUT: status.HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_REFERENCE: status.HTTP_400_BAD_REQUEST,
    ErrorCode.INVALID_PLAN: status.HTTP_400_BAD_REQUEST,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.PLAN_CONFLICT: status.HTTP_409_CONFLICT,
}


async def handle_request_validation_error(
    _request: Request, _exc: RequestValidationError,
) -> JSONResponse:
    response = ApiResponse[None].fail(
        ErrorCode.INVALID_INPUT.value, "요청 값이 올바르지 않습니다.",
    )
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content=response.model_dump(mode="json"),
    )


async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    status_code = APP_ERROR_STATUS.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    message = exc.message
    if status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("Application error: %s", exc.code.value, exc_info=exc)
        message = "요청을 처리하는 중 서버 오류가 발생했습니다."

    response = ApiResponse[None].fail(exc.code.value, message)
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))
