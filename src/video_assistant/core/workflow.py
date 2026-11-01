"""Application boundary: upload, orchestration, validation, and result lookup."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from pydantic import ValidationError

from .errors import AppError, ErrorCode
from .interfaces import (
    ApplicationService, ContentAnalyzer, JobScheduler, PlanService, ProjectStore,
    SegmentRecommender, Transcriber, VideoEditor,
)
from .media import probe_mp4
from .models import (
    ApprovedEditPlan, ClipSelection, EditPlan, JobKind, JobStage,
    JobStatus, PlanStatus, RecommendationResult, RenderResult,
    SearchRequest, Transcript, VideoAnalysis, VideoAsset,
)


class DefaultApplicationService(ApplicationService):
    def __init__(
        self, store: ProjectStore, plans: PlanService, scheduler: JobScheduler,
        transcriber: Transcriber, analyzer: ContentAnalyzer,
        recommender: SegmentRecommender, editor: VideoEditor,
        runtime_dir: Path, max_upload_mb: int = 200,
    ) -> None:
        self.store = store
        self.plans = plans
        self.scheduler = scheduler
        self.transcriber = transcriber
        self.analyzer = analyzer
        self.recommender = recommender
        self.editor = editor
        self.runtime_dir = runtime_dir.resolve()
        self.max_upload_bytes = max_upload_mb * 1024 * 1024

    @staticmethod
    def _version(module: object) -> str:
        version = getattr(module, "VERSION", None)
        if not isinstance(version, str) or not version:
            raise AppError(ErrorCode.INVALID_INPUT, "모듈은 캐시용 VERSION 문자열을 정의해야 합니다.")
        return version

    @staticmethod
    def _error(code: ErrorCode, action: str, exc: Exception) -> AppError:
        if isinstance(exc, AppError):
            return exc
        return AppError(code, f"{action} 도중 오류가 발생했습니다.")

    def ingest(self, file_name: str, stream: BinaryIO) -> VideoAsset:
        if Path(file_name).suffix.lower() != ".mp4":
            raise AppError(ErrorCode.INVALID_INPUT, "MVP는 .mp4 파일만 지원합니다.")
        video_id = uuid4().hex
        project_id = uuid4().hex
        project_dir = self.runtime_dir / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        destination = project_dir / "source.mp4"
        digest = hashlib.sha256()
        total = 0
        try:
            if hasattr(stream, "seek"):
                stream.seek(0)
            with destination.open("wb") as target:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > self.max_upload_bytes:
                        raise AppError(ErrorCode.INVALID_INPUT, "업로드 크기 제한을 초과했습니다.")
                    digest.update(chunk)
                    target.write(chunk)
            if total == 0:
                raise AppError(ErrorCode.INVALID_INPUT, "빈 파일은 업로드할 수 없습니다.")
            duration_ms, has_audio = probe_mp4(destination)
            video = VideoAsset(
                id=video_id, project_id=project_id, source_path=destination,
                original_name=Path(file_name).name, duration_ms=duration_ms,
                sha256=digest.hexdigest(), has_audio=has_audio,
            )
            self.store.save_video(video)
            return video
        except (OSError, AppError) as exc:
            destination.unlink(missing_ok=True)
            if isinstance(exc, AppError):
                raise
            raise AppError(ErrorCode.STORAGE_FAILED, "업로드 파일을 저장할 수 없습니다.") from exc

    def _check_transcript(self, transcript: Transcript, video: VideoAsset) -> None:
        if transcript.video_id != video.id or transcript.transcriber_version != self._version(self.transcriber):
            raise AppError(ErrorCode.TRANSCRIPTION_FAILED, "음성 인식 결과의 영상/버전 참조가 다릅니다.")
        if any(seg.end_ms > video.duration_ms for seg in transcript.segments):
            raise AppError(ErrorCode.TRANSCRIPTION_FAILED, "자막 구간이 영상 길이를 벗어났습니다.")

    def _check_analysis(self, analysis: VideoAnalysis, transcript: Transcript, video: VideoAsset) -> None:
        if (analysis.video_id, analysis.transcript_id, analysis.analyzer_version) != (video.id, transcript.id, self._version(self.analyzer)):
            raise AppError(ErrorCode.ANALYSIS_FAILED, "분석 결과의 영상/자막/버전 참조가 다릅니다.")
        known = {seg.id for seg in transcript.segments}
        if any(topic.end_ms > video.duration_ms or not set(topic.segment_ids).issubset(known) for topic in analysis.topics):
            raise AppError(ErrorCode.ANALYSIS_FAILED, "분석 결과의 주제 범위나 자막 참조가 잘못되었습니다.")

    def _check_recommendation(
        self, result: RecommendationResult, request: SearchRequest,
        transcript: Transcript, analysis: VideoAnalysis, video: VideoAsset,
    ) -> None:
        if (
            result.request_id, result.video_id, result.transcript_id,
            result.analysis_id, result.recommender_version,
        ) != (
            request.id, video.id, transcript.id, analysis.id, self._version(self.recommender),
        ):
            raise AppError(ErrorCode.RECOMMENDATION_FAILED, "추천 결과의 참조 정보가 올바르지 않습니다.")
        known = {seg.id for seg in transcript.segments}
        if len(result.clips) > request.max_clips or any(
            clip.end_ms > video.duration_ms or not set(clip.source_segment_ids).issubset(known)
            for clip in result.clips
        ):
            raise AppError(ErrorCode.RECOMMENDATION_FAILED, "추천 구간의 개수·시간·자막 참조가 올바르지 않습니다.")

    def _job(self, kind: JobKind, video: VideoAsset) -> JobStatus:
        return JobStatus(id=uuid4().hex, kind=kind, project_id=video.project_id, video_id=video.id)

    def get_video(self, video_id: str) -> VideoAsset:
        return self.store.get_video(video_id)

    def submit_prepare(self, video_id: str) -> JobStatus:
        video = self.store.get_video(video_id)
        job = self._job(JobKind.PREPARE, video)

        def task() -> str:
            self.scheduler.report(job.id, JobStage.TRANSCRIBING, 10)
            transcript = self.store.find_transcript(video.id, self._version(self.transcriber))
            if transcript is None:
                try:
                    transcript = self.transcriber.transcribe(video)
                    self._check_transcript(transcript, video)
                    self.store.save_transcript(transcript)
                except Exception as exc:
                    raise self._error(ErrorCode.TRANSCRIPTION_FAILED, "음성 인식", exc) from exc
            else:
                self._check_transcript(transcript, video)

            self.scheduler.report(job.id, JobStage.ANALYZING, 55)
            analysis = self.store.find_analysis(video.id, transcript.id, self._version(self.analyzer))
            if analysis is None:
                try:
                    analysis = self.analyzer.analyze(transcript)
                    self._check_analysis(analysis, transcript, video)
                    self.store.save_analysis(analysis)
                except Exception as exc:
                    raise self._error(ErrorCode.ANALYSIS_FAILED, "내용 분석", exc) from exc
            else:
                self._check_analysis(analysis, transcript, video)
            return analysis.id

        self.scheduler.submit(job, task)
        return job

    def submit_recommend(self, request: SearchRequest) -> JobStatus:
        video = self.store.get_video(request.video_id)
        transcript = self.get_transcript(video.id)
        analysis = self.get_analysis(video.id)
        if transcript is None or analysis is None:
            raise AppError(ErrorCode.INVALID_INPUT, "먼저 영상 준비(자막·분석)를 완료해 주세요.")
        self.store.save_request(request)
        job = self._job(JobKind.RECOMMEND, video)

        def task() -> str:
            self.scheduler.report(job.id, JobStage.RECOMMENDING, 20)
            try:
                result = self.recommender.recommend(request, transcript, analysis)
                self._check_recommendation(result, request, transcript, analysis, video)
                self.store.save_recommendation(result)
                return result.id
            except Exception as exc:
                raise self._error(ErrorCode.RECOMMENDATION_FAILED, "구간 추천", exc) from exc

        self.scheduler.submit(job, task)
        return job

    def create_plan(self, recommendation_id: str) -> EditPlan:
        return self.plans.create_draft(recommendation_id)

    def revise_plan(self, plan_id: str, expected_version: int, clips: tuple[ClipSelection, ...]) -> EditPlan:
        return self.plans.revise(plan_id, expected_version, clips)

    def approve_plan(self, plan_id: str, expected_version: int) -> ApprovedEditPlan:
        return self.plans.approve(plan_id, expected_version)

    def submit_render(self, plan_id: str, expected_version: int) -> JobStatus:
        plan = self.plans.get_plan(plan_id)
        if plan.version != expected_version or plan.status != PlanStatus.APPROVED:
            raise AppError(ErrorCode.PLAN_CONFLICT, "최신 승인된 편집 계획만 실행할 수 있습니다.")
        approved = ApprovedEditPlan.model_validate(plan.model_dump())
        video = self.store.get_video(approved.video_id)
        job = self._job(JobKind.RENDER, video)
        output_path = self.runtime_dir / "projects" / video.project_id / "outputs" / f"render_{job.id}.mp4"
        if not video.source_path.resolve().is_relative_to(self.runtime_dir):
            raise AppError(ErrorCode.INVALID_INPUT, "영상 파일이 관리 경로 밖에 있습니다.")

        def task() -> str:
            self.scheduler.report(job.id, JobStage.RENDERING, 15)
            try:
                result = self.editor.render(video, approved, output_path)
                self.scheduler.report(job.id, JobStage.VALIDATING, 90)
                if (
                    result.video_id, result.plan_id, result.plan_version
                ) != (video.id, approved.id, approved.version) or result.output_path.resolve() != output_path.resolve():
                    raise AppError(ErrorCode.OUTPUT_INVALID, "출력 영상의 계획 참조 또는 경로가 다릅니다.")
                actual_duration, _ = probe_mp4(output_path)
                if abs(actual_duration - result.duration_ms) > 100:
                    raise AppError(ErrorCode.OUTPUT_INVALID, "출력 영상 길이 정보가 FFprobe와 일치하지 않습니다.")
                self.store.save_render_result(result)
                return result.id
            except Exception as exc:
                raise self._error(ErrorCode.RENDER_FAILED, "영상 편집", exc) from exc

        self.scheduler.submit(job, task)
        return job

    def get_job(self, job_id: str) -> JobStatus:
        return self.scheduler.store.get_job(job_id)

    def get_transcript(self, video_id: str) -> Transcript | None:
        return self.store.find_transcript(video_id, self._version(self.transcriber))

    def get_analysis(self, video_id: str) -> VideoAnalysis | None:
        transcript = self.get_transcript(video_id)
        if transcript is None:
            return None
        return self.store.find_analysis(video_id, transcript.id, self._version(self.analyzer))

    def get_recommendation(self, recommendation_id: str) -> RecommendationResult:
        return self.store.get_recommendation(recommendation_id)

    def get_plan(self, plan_id: str, version: int | None = None) -> EditPlan:
        return self.plans.get_plan(plan_id, version)

    def get_render_result(self, result_id: str) -> RenderResult:
        return self.store.get_render_result(result_id)
