"""Single-process JSON store. Files use atomic replace and an in-process RLock.

This is intentionally NOT a multi-process transactional datastore.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from uuid import uuid4

from .errors import AppError, ErrorCode
from .interfaces import JobStore, ProjectStore
from .models import (
    EditPlan, JobStatus, PlanStatus, RecommendationResult, RenderResult,
    SearchRequest, Transcript, VideoAnalysis, VideoAsset,
)

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


class FileProjectStore(ProjectStore, JobStore):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def project_dir(self, project_id: str) -> Path:
        self._key(project_id)
        result = self.root / "projects" / project_id
        result.mkdir(parents=True, exist_ok=True)
        return result

    @staticmethod
    def _key(value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise AppError(ErrorCode.INVALID_INPUT, "잘못된 식별자 형식입니다.")
        return value

    def _file(self, kind: str, entity_id: str) -> Path:
        self._key(entity_id)
        return self.root / "records" / kind / f"{entity_id}.json"

    @staticmethod
    def _write(path: Path, model: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(model.model_dump_json(indent=2), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _read(path: Path, model_type: type):
        if not path.is_file():
            raise AppError(ErrorCode.NOT_FOUND, "요청한 데이터를 찾을 수 없습니다.")
        try:
            return model_type.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AppError(ErrorCode.STORAGE_FAILED, "저장된 데이터를 읽을 수 없습니다.") from exc

    def _save(self, kind: str, obj) -> None:
        with self._lock:
            self._write(self._file(kind, obj.id), obj)

    def _get(self, kind: str, id_: str, cls):
        with self._lock:
            return self._read(self._file(kind, id_), cls)

    def _find(self, kind: str, cls, predicate):
        with self._lock:
            folder = self.root / "records" / kind
            for path in sorted(folder.glob("*.json"), reverse=True):
                result = self._read(path, cls)
                if predicate(result):
                    return result
        return None

    def save_video(self, video: VideoAsset) -> None:
        self._save("videos", video)

    def get_video(self, video_id: str) -> VideoAsset:
        return self._get("videos", video_id, VideoAsset)

    def save_transcript(self, transcript: Transcript) -> None:
        self._save("transcripts", transcript)

    def get_transcript(self, transcript_id: str) -> Transcript:
        return self._get("transcripts", transcript_id, Transcript)

    def find_transcript(self, video_id: str, transcriber_version: str) -> Transcript | None:
        return self._find("transcripts", Transcript, lambda t: t.video_id == video_id and t.transcriber_version == transcriber_version)

    def save_analysis(self, analysis: VideoAnalysis) -> None:
        self._save("analyses", analysis)

    def get_analysis(self, analysis_id: str) -> VideoAnalysis:
        return self._get("analyses", analysis_id, VideoAnalysis)

    def find_analysis(self, video_id: str, transcript_id: str, analyzer_version: str) -> VideoAnalysis | None:
        return self._find("analyses", VideoAnalysis, lambda a: a.video_id == video_id and a.transcript_id == transcript_id and a.analyzer_version == analyzer_version)

    def save_request(self, request: SearchRequest) -> None:
        self._save("requests", request)

    def get_request(self, request_id: str) -> SearchRequest:
        return self._get("requests", request_id, SearchRequest)

    def save_recommendation(self, result: RecommendationResult) -> None:
        self._save("recommendations", result)

    def get_recommendation(self, recommendation_id: str) -> RecommendationResult:
        return self._get("recommendations", recommendation_id, RecommendationResult)

    def _plan_current(self, plan_id: str) -> Path:
        return self.root / "records" / "plans" / self._key(plan_id) / "current.json"

    def save_plan(self, plan: EditPlan, expected_version: int | None, expected_status: PlanStatus | None) -> None:
        with self._lock:
            current_file = self._plan_current(plan.id)
            if expected_version is None and expected_status is None:
                if current_file.exists():
                    raise AppError(ErrorCode.PLAN_CONFLICT, "이미 존재하는 편집 계획입니다.")
                if plan.version != 1 or plan.status != PlanStatus.DRAFT:
                    raise AppError(ErrorCode.INVALID_PLAN, "새 계획은 1번 초안이어야 합니다.")
            else:
                current = self._read(current_file, EditPlan)
                if current.version != expected_version or current.status != expected_status:
                    raise AppError(ErrorCode.PLAN_CONFLICT, "편집 계획이 다른 요청에 의해 변경되었습니다.")
                if plan.id != current.id or (plan.video_id, plan.request_id, plan.recommendation_id) != (current.video_id, current.request_id, current.recommendation_id):
                    raise AppError(ErrorCode.INVALID_PLAN, "계획의 원본 참조를 변경할 수 없습니다.")
                if current.status != PlanStatus.DRAFT:
                    raise AppError(ErrorCode.PLAN_CONFLICT, "승인된 계획은 수정할 수 없습니다.")
                if plan.status == PlanStatus.DRAFT and plan.version != current.version + 1:
                    raise AppError(ErrorCode.INVALID_PLAN, "초안 수정 시 버전은 1 증가해야 합니다.")
                if plan.status == PlanStatus.APPROVED and (plan.version != current.version or plan.clips != current.clips):
                    raise AppError(ErrorCode.INVALID_PLAN, "승인은 현재 버전과 클립을 유지해야 합니다.")
            version_file = current_file.parent / f"v{plan.version}.json"
            self._write(version_file, plan)
            self._write(current_file, plan)

    def get_plan(self, plan_id: str, version: int | None = None) -> EditPlan:
        with self._lock:
            path = self._plan_current(plan_id)
            if version is not None:
                if version < 1:
                    raise AppError(ErrorCode.INVALID_INPUT, "잘못된 편집 계획 버전입니다.")
                path = path.parent / f"v{version}.json"
            return self._read(path, EditPlan)

    def save_render_result(self, result: RenderResult) -> None:
        self._save("renders", result)

    def get_render_result(self, result_id: str) -> RenderResult:
        return self._get("renders", result_id, RenderResult)

    def create_job(self, status: JobStatus) -> None:
        with self._lock:
            if self._file("jobs", status.id).exists():
                raise AppError(ErrorCode.STORAGE_FAILED, "이미 존재하는 작업입니다.")
            self._write(self._file("jobs", status.id), status)

    def save_job(self, status: JobStatus) -> None:
        with self._lock:
            self._read(self._file("jobs", status.id), JobStatus)
            self._write(self._file("jobs", status.id), status)

    def get_job(self, job_id: str) -> JobStatus:
        return self._get("jobs", job_id, JobStatus)

    def recover_interrupted_jobs(self) -> None:
        """Run once at startup in a single-process deployment."""
        from .models import JobState, utc_now

        with self._lock:
            folder = self.root / "records" / "jobs"
            for path in folder.glob("*.json"):
                job = self._read(path, JobStatus)
                if job.state in (JobState.QUEUED, JobState.RUNNING):
                    failed = JobStatus.model_validate({
                        **job.model_dump(), "state": JobState.FAILED,
                        "error_code": ErrorCode.WORKER_FAILED.value,
                        "error_message": "프로그램 재시작으로 작업이 중단되었습니다. 다시 실행해 주세요.",
                        "finished_at": utc_now(),
                    })
                    self._write(path, failed)
