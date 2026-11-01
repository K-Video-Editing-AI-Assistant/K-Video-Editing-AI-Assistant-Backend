"""One in-process worker; persisted status; no Streamlit calls."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from typing import Callable

from .errors import AppError, ErrorCode
from .interfaces import JobScheduler, JobStore
from .models import JobStage, JobState, JobStatus, utc_now

_LOG = logging.getLogger(__name__)


class ThreadJobScheduler(JobScheduler):
    def __init__(self, store: JobStore, max_workers: int = 1) -> None:
        self.store = store
        self._lock = RLock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="video-worker")

    def submit(self, initial_status: JobStatus, task: Callable[[], str]) -> None:
        self.store.create_job(initial_status)
        try:
            self._pool.submit(self._execute, initial_status.id, task)
        except RuntimeError as exc:
            failed = JobStatus.model_validate({
                **initial_status.model_dump(), "state": JobState.FAILED,
                "error_code": ErrorCode.WORKER_FAILED.value,
                "error_message": "작업자를 시작할 수 없습니다.", "finished_at": utc_now(),
            })
            self.store.save_job(failed)
            raise AppError(ErrorCode.WORKER_FAILED, "작업자를 시작할 수 없습니다.") from exc

    def _execute(self, job_id: str, task: Callable[[], str]) -> None:
        with self._lock:
            status = self.store.get_job(job_id)
            status = JobStatus.model_validate({
                **status.model_dump(), "state": JobState.RUNNING,
                "started_at": utc_now(), "progress": 0,
            })
            self.store.save_job(status)
        try:
            result_id = task()
            with self._lock:
                current = self.store.get_job(job_id)
                succeeded = JobStatus.model_validate({
                    **current.model_dump(), "state": JobState.SUCCEEDED,
                    "progress": 100, "result_ref": result_id, "finished_at": utc_now(),
                })
                self.store.save_job(succeeded)
        except Exception as exc:
            # All exceptions are caught here so the UI sees a terminal state.
            if isinstance(exc, AppError):
                code = exc.code.value
                message = exc.message
            else:
                code = ErrorCode.WORKER_FAILED.value
                message = "작업 처리 중 오류가 발생했습니다. 서버 로그를 확인하세요."
            _LOG.exception("Worker failed: job=%s", job_id)
            with self._lock:
                current = self.store.get_job(job_id)
                failed = JobStatus.model_validate({
                    **current.model_dump(), "state": JobState.FAILED,
                    "error_code": code, "error_message": message,
                    "finished_at": utc_now(),
                })
                self.store.save_job(failed)

    def report(self, job_id: str, stage: JobStage, progress: int | None) -> None:
        with self._lock:
            current = self.store.get_job(job_id)
            if current.state != JobState.RUNNING:
                raise AppError(ErrorCode.WORKER_FAILED, "실행 중인 작업만 진행률을 보고할 수 있습니다.")
            updated = JobStatus.model_validate({
                **current.model_dump(), "stage": stage, "progress": progress,
            })
            self.store.save_job(updated)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
