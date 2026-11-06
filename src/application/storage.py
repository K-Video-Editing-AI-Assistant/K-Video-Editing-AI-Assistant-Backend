"""Application 담당: JSON metadata repository for the single-process MVP.

Project relationships belong here. Binary video handling belongs to processing/files.py.
Writes are atomic inside the current process; cross-process concurrent writes are unsupported.
"""

import os
import re
from pathlib import Path
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel

from core.errors import AppError, ErrorCode
from core.models import (
    EditPlan, ProcessedTranscript, Project, ProjectAnalysis, RecommendationResult,
    RenderResult, SearchRequest, Transcript, VideoAnalysis, VideoAsset,
)


class ProjectStore:
    """Read/write project-scoped Pydantic models without mutating them in place."""

    def __init__(self, runtime_dir: Path):
        self.root = Path(runtime_dir).resolve() / "projects"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def project_dir(self, project_id: str) -> Path:
        self._check_id(project_id)
        return self.root / project_id

    def video_dir(self, project_id: str, video_id: str) -> Path:
        self._check_id(video_id)
        return self.project_dir(project_id) / "videos" / video_id

    def output_path(self, project_id: str, plan: EditPlan) -> Path:
        return self.project_dir(project_id) / "outputs" / f"{plan.id}_v{plan.version}.mp4"

    @staticmethod
    def _check_id(value: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", value):
            raise AppError(ErrorCode.INVALID_INPUT, "식별자는 UUID hex 형식이어야 합니다.")

    def _write(self, path: Path, value: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".{uuid4().hex}.tmp")
        try:
            tmp.write_text(value.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    @staticmethod
    def _read(path: Path, kind):
        try:
            return kind.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AppError(ErrorCode.NOT_FOUND, f"저장된 데이터를 찾을 수 없습니다: {path.name}") from exc

    def save_project(self, project: Project) -> None:
        with self.lock:
            self._write(self.project_dir(project.id) / "project.json", project)

    def project(self, project_id: str) -> Project:
        with self.lock:
            return self._read(self.project_dir(project_id) / "project.json", Project)

    def invalidate_project_results(self, project_id: str) -> None:
        """A newly added source invalidates project-wide analysis, recommendation and plan.

        Historical per-request files remain for debugging; only current pointers are cleared.
        """
        with self.lock:
            folder = self.project_dir(project_id)
            for name in ("project_analysis.json", "latest_recommendation.json",
                         "latest_plan.json", "latest_render.json"):
                (folder / name).unlink(missing_ok=True)

    def save_video(self, video: VideoAsset) -> None:
        with self.lock:
            self._write(self.video_dir(video.project_id, video.id) / "video.json", video)

    def video(self, project_id: str, video_id: str) -> VideoAsset:
        with self.lock:
            video = self._read(self.video_dir(project_id, video_id) / "video.json", VideoAsset)
            expected = (self.video_dir(project_id, video_id) / "source.mp4").resolve()
            if video.id != video_id or video.project_id != project_id or video.source_path.resolve() != expected:
                raise AppError(ErrorCode.INVALID_REFERENCE, "영상의 저장 경로 또는 ID가 유효하지 않습니다.")
            if not expected.is_file():
                raise AppError(ErrorCode.NOT_FOUND, "영상 원본 파일이 없습니다.")
            return video

    def _video_record_path(self, project_id: str, video_id: str, name: str) -> Path:
        return self.video_dir(project_id, video_id) / f"{name}.json"

    def save_video_data(self, project_id: str, video_id: str, name: str, value: BaseModel) -> None:
        if name not in {"transcript", "processed", "analysis"}:
            raise ValueError("unknown video data name")
        with self.lock:
            self._write(self._video_record_path(project_id, video_id, name), value)

    def video_data(self, project_id: str, video_id: str, name: str):
        models = {"transcript": Transcript, "processed": ProcessedTranscript, "analysis": VideoAnalysis}
        with self.lock:
            return self._read(self._video_record_path(project_id, video_id, name), models[name])

    def save_project_analysis(self, analysis: ProjectAnalysis) -> None:
        with self.lock:
            self._write(self.project_dir(analysis.project_id) / "project_analysis.json", analysis)

    def project_analysis(self, project_id: str) -> ProjectAnalysis:
        with self.lock:
            return self._read(self.project_dir(project_id) / "project_analysis.json", ProjectAnalysis)

    def save_recommendation(self, request: SearchRequest, result: RecommendationResult) -> None:
        with self.lock:
            folder = self.project_dir(result.project_id) / "recommendations"
            self._write(folder / f"{request.id}_request.json", request)
            self._write(folder / f"{result.id}.json", result)
            self._write(self.project_dir(result.project_id) / "latest_recommendation.json", result)

    def recommendation(self, project_id: str, recommendation_id: str) -> RecommendationResult:
        self._check_id(recommendation_id)
        with self.lock:
            return self._read(self.project_dir(project_id) / "recommendations" /
                              f"{recommendation_id}.json", RecommendationResult)

    def latest_recommendation(self, project_id: str) -> RecommendationResult:
        return self._read(self.project_dir(project_id) / "latest_recommendation.json", RecommendationResult)

    def save_plan(self, plan: EditPlan) -> None:
        """Persist the current plan and an immutable-named version snapshot."""
        with self.lock:
            folder = self.project_dir(plan.project_id) / "plans"
            suffix = "approved" if plan.status.value == "approved" else "draft"
            self._write(folder / f"{plan.id}_v{plan.version}_{suffix}.json", plan)
            self._write(self.project_dir(plan.project_id) / "latest_plan.json", plan)

    def plan(self, project_id: str) -> EditPlan:
        with self.lock:
            return self._read(self.project_dir(project_id) / "latest_plan.json", EditPlan)

    def save_render(self, result: RenderResult) -> None:
        with self.lock:
            self._write(self.project_dir(result.project_id) / "latest_render.json", result)

    def render(self, project_id: str) -> RenderResult:
        with self.lock:
            return self._read(self.project_dir(project_id) / "latest_render.json", RenderResult)
