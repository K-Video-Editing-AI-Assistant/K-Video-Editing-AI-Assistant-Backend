"""Application 담당: single internal worker + JSON-persisted job status.

Queued/running jobs from a previous session become FAILED on restart; they are
not automatically resumed. Suitable for one developer process, not multi-worker hosting.
"""

import os
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from typing import Callable
from uuid import uuid4

from core.errors import AppError, ErrorCode
from core.models import JobKind, JobState, JobStatus, new_id, utc_now


class JobStore:
    def __init__(self, runtime_dir: Path):
        self.root = Path(runtime_dir).resolve() / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self._recover()

    def _path(self, job_id: str) -> Path:
        if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
            raise AppError(ErrorCode.INVALID_INPUT, "잘못된 작업 ID")
        return self.root / f"{job_id}.json"

    def save(self, job: JobStatus) -> None:
        with self.lock:
            path = self._path(job.id)
            temp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
            try:
                temp.write_text(job.model_dump_json(indent=2), encoding="utf-8")
                os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)

    def load(self, job_id: str) -> JobStatus:
        with self.lock:
            try:
                return JobStatus.model_validate_json(self._path(job_id).read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise AppError(ErrorCode.NOT_FOUND, "작업 ID를 찾을 수 없습니다.") from exc

    def _recover(self) -> None:
        for path in self.root.glob("*.json"):
            try:
                old = JobStatus.model_validate_json(path.read_text(encoding="utf-8"))
                if old.state in (JobState.QUEUED, JobState.RUNNING):
                    self.save(JobStatus.model_validate({
                        **old.model_dump(), "state": JobState.FAILED,
                        "error_message": "프로그램 종료로 작업이 중단되었습니다.",
                        "updated_at": utc_now(),
                    }))
            except (ValueError, OSError):
                continue


class JobScheduler:
    def __init__(self, store: JobStore):
        self.store = store
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clipnote-job")
        self.lock = RLock()
        self.futures: dict[str, Future] = {}

    def submit(self, kind: JobKind, project_id: str, func: Callable[[], str]) -> JobStatus:
        status = JobStatus(id=new_id(), project_id=project_id, kind=kind)
        self.store.save(status)

        def task() -> None:
            self.store.save(JobStatus.model_validate({
                **status.model_dump(), "state": JobState.RUNNING, "progress": 10,
                "updated_at": utc_now(),
            }))
            try:
                result_id = func()
                finished = JobStatus.model_validate({
                    **status.model_dump(), "state": JobState.SUCCEEDED,
                    "progress": 100, "result_ref": result_id, "updated_at": utc_now(),
                })
            except Exception as exc:
                finished = JobStatus.model_validate({
                    **status.model_dump(), "state": JobState.FAILED,
                    "error_message": str(exc), "updated_at": utc_now(),
                })
            self.store.save(finished)

        with self.lock:
            self.futures[status.id] = self.worker.submit(task)
        return status

    def get(self, job_id: str) -> JobStatus:
        return self.store.load(job_id)

    def shutdown(self) -> None:
        self.worker.shutdown(wait=True)
