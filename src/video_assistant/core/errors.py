"""Stable public error codes and the application-layer exception type."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    TRANSCRIPTION_FAILED = "transcription_failed"
    ANALYSIS_FAILED = "analysis_failed"
    RECOMMENDATION_FAILED = "recommendation_failed"
    INVALID_PLAN = "invalid_plan"
    PLAN_CONFLICT = "plan_conflict"
    RENDER_FAILED = "render_failed"
    OUTPUT_INVALID = "output_invalid"
    WORKER_FAILED = "worker_failed"
    RESOURCE_BUSY = "resource_busy"
    STORAGE_FAILED = "storage_failed"


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
