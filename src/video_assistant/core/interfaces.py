"""Public ports. Concrete implementations live outside core."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Callable

from .models import (
    ApprovedEditPlan, ClipSelection, EditPlan, JobStage, JobStatus, PlanStatus,
    RecommendationResult, RenderResult, SearchRequest, Transcript,
    VideoAnalysis, VideoAsset,
)


class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, video: VideoAsset) -> Transcript:
        """Create a transcript; an empty segments tuple is valid for silence."""


class ContentAnalyzer(ABC):
    @abstractmethod
    def analyze(self, transcript: Transcript) -> VideoAnalysis:
        """Produce reusable analysis from the transcript only."""


class SegmentRecommender(ABC):
    @abstractmethod
    def recommend(
        self, request: SearchRequest, transcript: Transcript, analysis: VideoAnalysis
    ) -> RecommendationResult:
        """Return ordered suggestions; an empty clips tuple means no matches."""


class VideoEditor(ABC):
    @abstractmethod
    def render(
        self, video: VideoAsset, plan: ApprovedEditPlan, output_path: Path
    ) -> RenderResult:
        """Render an approved plan and verify the resulting MP4 with FFprobe."""


class ProjectStore(ABC):
    @abstractmethod
    def save_video(self, video: VideoAsset) -> None:
        pass

    @abstractmethod
    def get_video(self, video_id: str) -> VideoAsset:
        pass

    @abstractmethod
    def save_transcript(self, transcript: Transcript) -> None:
        pass

    @abstractmethod
    def get_transcript(self, transcript_id: str) -> Transcript:
        pass

    @abstractmethod
    def find_transcript(self, video_id: str, transcriber_version: str) -> Transcript | None:
        pass

    @abstractmethod
    def save_analysis(self, analysis: VideoAnalysis) -> None:
        pass

    @abstractmethod
    def get_analysis(self, analysis_id: str) -> VideoAnalysis:
        pass

    @abstractmethod
    def find_analysis(
        self, video_id: str, transcript_id: str, analyzer_version: str
    ) -> VideoAnalysis | None:
        pass

    @abstractmethod
    def save_request(self, request: SearchRequest) -> None:
        pass

    @abstractmethod
    def get_request(self, request_id: str) -> SearchRequest:
        pass

    @abstractmethod
    def save_recommendation(self, result: RecommendationResult) -> None:
        pass

    @abstractmethod
    def get_recommendation(self, recommendation_id: str) -> RecommendationResult:
        pass

    @abstractmethod
    def save_plan(
        self, plan: EditPlan, expected_version: int | None,
        expected_status: PlanStatus | None
    ) -> None:
        """Atomically compare version AND status; on creation both are None."""

    @abstractmethod
    def get_plan(self, plan_id: str, version: int | None = None) -> EditPlan:
        pass

    @abstractmethod
    def save_render_result(self, result: RenderResult) -> None:
        pass

    @abstractmethod
    def get_render_result(self, result_id: str) -> RenderResult:
        pass


class JobStore(ABC):
    @abstractmethod
    def create_job(self, status: JobStatus) -> None:
        pass

    @abstractmethod
    def save_job(self, status: JobStatus) -> None:
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> JobStatus:
        pass


class JobScheduler(ABC):
    @abstractmethod
    def submit(self, initial_status: JobStatus, task: Callable[[], str]) -> None:
        """Schedule a task returning the result ID; never call Streamlit APIs in task."""

    @abstractmethod
    def report(self, job_id: str, stage: JobStage, progress: int | None) -> None:
        """Persist stage/progress updates from worker-side application logic."""


class PlanService(ABC):
    @abstractmethod
    def create_draft(self, recommendation_id: str) -> EditPlan:
        pass

    @abstractmethod
    def revise(
        self, plan_id: str, expected_version: int, clips: tuple[ClipSelection, ...]
    ) -> EditPlan:
        pass

    @abstractmethod
    def approve(self, plan_id: str, expected_version: int) -> ApprovedEditPlan:
        pass

    @abstractmethod
    def get_plan(self, plan_id: str, version: int | None = None) -> EditPlan:
        pass


class ApplicationService(ABC):
    @abstractmethod
    def ingest(self, file_name: str, stream: BinaryIO) -> VideoAsset:
        """Copy the upload to stable storage and probe it before returning."""

    @abstractmethod
    def get_video(self, video_id: str) -> VideoAsset:
        pass

    @abstractmethod
    def submit_prepare(self, video_id: str) -> JobStatus:
        pass

    @abstractmethod
    def submit_recommend(self, request: SearchRequest) -> JobStatus:
        pass

    @abstractmethod
    def create_plan(self, recommendation_id: str) -> EditPlan:
        pass

    @abstractmethod
    def revise_plan(
        self, plan_id: str, expected_version: int, clips: tuple[ClipSelection, ...]
    ) -> EditPlan:
        pass

    @abstractmethod
    def approve_plan(self, plan_id: str, expected_version: int) -> ApprovedEditPlan:
        pass

    @abstractmethod
    def submit_render(self, plan_id: str, expected_version: int) -> JobStatus:
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> JobStatus:
        pass

    @abstractmethod
    def get_transcript(self, video_id: str) -> Transcript | None:
        pass

    @abstractmethod
    def get_analysis(self, video_id: str) -> VideoAnalysis | None:
        pass

    @abstractmethod
    def get_recommendation(self, recommendation_id: str) -> RecommendationResult:
        pass

    @abstractmethod
    def get_plan(self, plan_id: str, version: int | None = None) -> EditPlan:
        pass

    @abstractmethod
    def get_render_result(self, result_id: str) -> RenderResult:
        pass
