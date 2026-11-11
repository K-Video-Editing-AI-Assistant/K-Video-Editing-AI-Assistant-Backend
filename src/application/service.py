"""Application 담당: Streamlit이 호출하는 단일 Python 서비스 진입점.

자신이 AI/Whisper/FFmpeg를 직접 구현하지 않고 공통 인터페이스를 사용합니다.
영상 준비 → 내용 분석 → 요청별 추천 → 편집 계획 승인 → 렌더링 순서를 관리합니다.
"""

import logging
from time import perf_counter
from threading import RLock

from application.jobs import JobScheduler
from application.plans import PlanService
from application.storage import ProjectStore
from core.errors import AppError, ErrorCode
from core.interfaces import (
    ContentAnalyzer, ProjectAnalyzer, SegmentRecommender, TranscriptPreprocessor,
    Transcriber, VideoEditor,
)
from core.models import (
    ApprovedEditPlan, EditPlan, JobKind, JobStatus, PlanClip, ProcessedTranscript,
    Project, ProjectAnalysis, RecommendationResult, RenderResult, SearchRequest,
    SubtitleStyle, Transcript, VideoAnalysis, VideoAsset, new_id, utc_now,
)
from processing.files import save_upload, write_srt


logger = logging.getLogger(__name__)


class ApplicationService:
    """Domain workflow and storage coordination; no web framework dependencies."""

    def __init__(
        self, store: ProjectStore, scheduler: JobScheduler, transcriber: Transcriber,
        preprocessor: TranscriptPreprocessor, analyzer: ContentAnalyzer,
        project_analyzer: ProjectAnalyzer, recommender: SegmentRecommender,
        editor: VideoEditor,
    ):
        self.store = store
        self.scheduler = scheduler
        self.transcriber = transcriber
        self.preprocessor = preprocessor
        self.analyzer = analyzer
        self.project_analyzer = project_analyzer
        self.recommender = recommender
        self.editor = editor
        self.plans = PlanService()
        self.lock = RLock()

    def create_project(self, title: str = "새 편집 프로젝트") -> Project:
        """Create an empty project before any video upload."""
        project = Project(id=new_id(), title=title)
        self.store.save_project(project)
        return project

    def get_project(self, project_id: str) -> Project:
        return self.store.project(project_id)

    def add_video(self, project_id: str, filename: str, contents: bytes) -> VideoAsset:
        """Store an MP4, probe duration and add its ID to the project."""
        with self.lock:
            project = self.get_project(project_id)
            video = save_upload(project.id, filename, contents, self.store.root.parent)
            self.store.save_video(video)
            updated = Project.model_validate({
                **project.model_dump(), "video_ids": (*project.video_ids, video.id),
                "updated_at": utc_now(),
            })
            self.store.save_project(updated)
            self.store.invalidate_project_results(project.id)
            return video

    def get_video(self, project_id: str, video_id: str) -> VideoAsset:
        self._require_video(project_id, video_id)
        return self.store.video(project_id, video_id)

    def _require_video(self, project_id: str, video_id: str) -> None:
        if video_id not in self.get_project(project_id).video_ids:
            raise AppError(ErrorCode.INVALID_REFERENCE, "영상이 프로젝트에 속하지 않습니다.")

    def _videos(self, project: Project) -> tuple[VideoAsset, ...]:
        return tuple(self.store.video(project.id, video_id) for video_id in project.video_ids)

    def prepare_video(self, project_id: str, video_id: str) -> VideoAnalysis:
        """영상 1개의 자막 추출·전처리·요약 및 주제 분석 결과를 저장하고 반환합니다."""
        video = self.get_video(project_id, video_id)
        started = perf_counter()
        logger.info("자막 추출 단계 시작")
        self.scheduler.report_stage("transcribing")
        try:
            transcript = self.store.video_data(project_id, video.id, "transcript")
            if transcript.transcriber_version != self.transcriber.VERSION:
                raise AppError(ErrorCode.NOT_FOUND, "Whisper 구현 버전 변경")
        except AppError as exc:
            if exc.code != ErrorCode.NOT_FOUND:
                raise
            transcript = self.transcriber.transcribe(video)
            self._validate_transcript(video, transcript)
            self.store.save_video_data(project_id, video.id, "transcript", transcript)
            write_srt(transcript, self.store.video_dir(project_id, video.id) / "transcript.srt")
        self._validate_transcript(video, transcript)
        logger.info("자막 추출 단계 완료 — %d개 구간, %.1f초 (캐시 사용 시 포함)", len(transcript.segments), perf_counter() - started)

        started = perf_counter()
        logger.info("자막 전처리 단계 시작")
        self.scheduler.report_stage("preprocessing")
        try:
            processed = self.store.video_data(project_id, video.id, "processed")
            if processed.source_transcript_id != transcript.id or processed.preprocessing_version != getattr(self.preprocessor, "cache_version", self.preprocessor.VERSION):
                raise AppError(ErrorCode.NOT_FOUND, "전처리 캐시 갱신 필요")
        except AppError as exc:
            if exc.code != ErrorCode.NOT_FOUND:
                raise
            processed = self.preprocessor.preprocess(transcript)
            self._validate_processed(transcript, processed)
            self.store.save_video_data(project_id, video.id, "processed", processed)
        self._validate_processed(transcript, processed)
        logger.info("자막 전처리 단계 완료 — %.1f초", perf_counter() - started)

        started = perf_counter()
        logger.info("요약·주제 분석 단계 시작")
        self.scheduler.report_stage("analyzing")
        try:
            analysis = self.store.video_data(project_id, video.id, "analysis")
            if (analysis.transcript_id != transcript.id
                    or analysis.processed_transcript_id != processed.id
                    or analysis.analyzer_version != getattr(self.analyzer, "cache_version", self.analyzer.VERSION)):
                raise AppError(ErrorCode.NOT_FOUND, "AI 분석 캐시 갱신 필요")
        except AppError as exc:
            if exc.code != ErrorCode.NOT_FOUND:
                raise
            analysis = self.analyzer.analyze(processed)
            self._validate_analysis(video, transcript, processed, analysis)
            self.store.save_video_data(project_id, video.id, "analysis", analysis)
        self._validate_analysis(video, transcript, processed, analysis)
        logger.info("요약·주제 분석 단계 완료 — %.1f초", perf_counter() - started)

        return analysis

    def prepare_project(self, project_id: str) -> ProjectAnalysis:
        """Whisper→전처리→영상 분석→전체 키워드. User queries can reuse these results."""
        project = self.get_project(project_id)
        if not project.video_ids:
            raise AppError(ErrorCode.INVALID_INPUT, "먼저 영상을 등록해야 합니다.")
        analyses = [
            self.prepare_video(project.id, video.id)
            for video in self._videos(project)
        ]

        # MVP: recompute project keywords each call; per-video transcript/analysis is cached.
        result = self.project_analyzer.analyze_project(project, tuple(analyses))
        if (result.project_id != project.id or
                result.video_analysis_ids != tuple(item.id for item in analyses)):
            raise AppError(ErrorCode.INVALID_REFERENCE, "프로젝트 분석 결과의 ID가 잘못되었습니다.")
        known_topics = {topic.id for analysis in analyses for topic in analysis.topics}
        for keyword in result.suggested_keywords:
            if not set(keyword.topic_ids).issubset(known_topics):
                raise AppError(ErrorCode.INVALID_REFERENCE, "키워드에 알 수 없는 주제가 있습니다.")
        self.store.save_project_analysis(result)
        return result

    @staticmethod
    def _validate_transcript(video: VideoAsset, transcript: Transcript) -> None:
        if transcript.video_id != video.id or transcript.transcriber_version == "":
            raise AppError(ErrorCode.INVALID_REFERENCE, "자막의 영상 ID가 잘못되었습니다.")
        if any(item.end_ms > video.duration_ms for item in transcript.segments):
            raise AppError(ErrorCode.INVALID_INPUT, "자막이 원본 영상 길이를 초과합니다.")

    @staticmethod
    def _validate_processed(transcript: Transcript, processed: ProcessedTranscript) -> None:
        if (processed.video_id != transcript.video_id or
                processed.source_transcript_id != transcript.id):
            raise AppError(ErrorCode.INVALID_REFERENCE, "전처리된 자막의 원본 ID가 잘못되었습니다.")
        by_id = {item.id: item for item in transcript.segments}
        for item in processed.segments:
            if not set(item.source_segment_ids).issubset(by_id):
                raise AppError(ErrorCode.INVALID_REFERENCE, "없는 원본 자막 ID를 참조합니다.")
            if (item.start_ms < min(by_id[s].start_ms for s in item.source_segment_ids)
                    or item.end_ms > max(by_id[s].end_ms for s in item.source_segment_ids)):
                raise AppError(ErrorCode.INVALID_REFERENCE, "전처리 구간이 원본 발언 시간과 다릅니다.")

    @staticmethod
    def _validate_analysis(
        video: VideoAsset, transcript: Transcript, processed: ProcessedTranscript,
        analysis: VideoAnalysis,
    ) -> None:
        if (analysis.video_id != video.id or analysis.transcript_id != transcript.id
                or analysis.processed_transcript_id != processed.id):
            raise AppError(ErrorCode.INVALID_REFERENCE, "AI 분석의 참조 ID가 일치하지 않습니다.")
        by_id = {item.id: item for item in transcript.segments}
        for topic in analysis.topics:
            if topic.end_ms > video.duration_ms or not set(topic.source_segment_ids).issubset(by_id):
                raise AppError(ErrorCode.INVALID_REFERENCE, "주제의 자막 참조 또는 시간이 잘못되었습니다.")
            if any(by_id[sid].end_ms <= topic.start_ms or by_id[sid].start_ms >= topic.end_ms
                   for sid in topic.source_segment_ids):
                raise AppError(ErrorCode.INVALID_REFERENCE, "주제 시간은 참조하는 발언과 겹쳐야 합니다.")

    def get_transcript(self, project_id: str, video_id: str) -> Transcript:
        self._require_video(project_id, video_id)
        return self.store.video_data(project_id, video_id, "transcript")

    def get_video_analysis(self, project_id: str, video_id: str) -> VideoAnalysis:
        self._require_video(project_id, video_id)
        return self.store.video_data(project_id, video_id, "analysis")

    def get_project_analysis(self, project_id: str) -> ProjectAnalysis:
        return self.store.project_analysis(project_id)

    def recommend(self, request: SearchRequest) -> RecommendationResult:
        """Use cached preparation results; do not run Whisper again for every request."""
        project = self.get_project(request.project_id)
        if not set(request.video_ids).issubset(project.video_ids):
            raise AppError(ErrorCode.INVALID_REFERENCE, "검색할 원본 영상 ID가 프로젝트에 없습니다.")
        project_analysis = self.store.project_analysis(project.id)
        transcripts = tuple(self.get_transcript(project.id, vid) for vid in request.video_ids)
        analyses = tuple(self.get_video_analysis(project.id, vid) for vid in request.video_ids)
        result = self.recommender.recommend(request, transcripts, analyses, project_analysis)
        if (result.project_id != project.id or result.request_id != request.id
                or result.project_analysis_id != project_analysis.id
                or result.recommender_version != self.recommender.VERSION
                or len(result.clips) > request.max_clips):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 결과 계약을 위반했습니다.")
        transcript_by_video = {item.video_id: item for item in transcripts}
        video_by_id = {video.id: video for video in self._videos(project)}
        for clip in result.clips:
            if clip.video_id not in transcript_by_video:
                raise AppError(ErrorCode.INVALID_REFERENCE, "선택하지 않은 영상에서 추천되었습니다.")
            by_id = {seg.id: seg for seg in transcript_by_video[clip.video_id].segments}
            if (clip.end_ms > video_by_id[clip.video_id].duration_ms or
                    not set(clip.source_segment_ids).issubset(by_id)):
                raise AppError(ErrorCode.INVALID_REFERENCE, "추천 시간 또는 발언 ID가 잘못되었습니다.")
            if any(by_id[sid].end_ms <= clip.start_ms or by_id[sid].start_ms >= clip.end_ms
                   for sid in clip.source_segment_ids):
                raise AppError(ErrorCode.INVALID_REFERENCE, "추천 시간과 근거 발언이 겹치지 않습니다.")
        self.store.save_recommendation(request, result)
        return result

    def get_recommendation(self, project_id: str, recommendation_id: str) -> RecommendationResult:
        return self.store.recommendation(project_id, recommendation_id)

    def latest_recommendation(self, project_id: str) -> RecommendationResult:
        return self.store.latest_recommendation(project_id)

    def create_plan(
        self, project_id: str, recommendation_id: str,
        subtitle_style: SubtitleStyle = SubtitleStyle.BASIC,
    ) -> EditPlan:
        with self.lock:
            project = self.get_project(project_id)
            result = self.get_recommendation(project_id, recommendation_id)
            current_analysis = self.get_project_analysis(project_id)
            if result.project_analysis_id != current_analysis.id:
                raise AppError(ErrorCode.INVALID_REFERENCE, "오래된 AI 분석에 대한 추천 결과입니다.")
            plan = self.plans.create(result, project, self._videos(project), subtitle_style)
            self.store.save_plan(plan)
            return plan

    def get_plan(self, project_id: str) -> EditPlan:
        return self.store.plan(project_id)

    def revise_plan(
        self, project_id: str, plan_id: str, expected_version: int,
        clips: tuple[PlanClip, ...],
    ) -> EditPlan:
        with self.lock:
            current = self.get_plan(project_id)
            if current.id != plan_id:
                raise AppError(ErrorCode.PLAN_CONFLICT, "다른 편집 계획을 수정하려고 합니다.")
            project = self.get_project(project_id)
            revised = self.plans.revise(current, expected_version, clips, project, self._videos(project))
            self.store.save_plan(revised)
            return revised

    def approve_plan(self, project_id: str, plan_id: str, expected_version: int) -> ApprovedEditPlan:
        with self.lock:
            current = self.get_plan(project_id)
            if current.id != plan_id:
                raise AppError(ErrorCode.PLAN_CONFLICT, "다른 편집 계획을 승인하려고 합니다.")
            project = self.get_project(project_id)
            approved = self.plans.approve(current, expected_version, project, self._videos(project))
            self.store.save_plan(approved)
            return approved

    def render(self, project_id: str, plan_id: str, expected_version: int) -> RenderResult:
        """Only an approved, current plan can reach FFmpeg/Stub editor."""
        with self.lock:
            current = self.get_plan(project_id)
            if current.id != plan_id or current.version != expected_version:
                raise AppError(ErrorCode.PLAN_CONFLICT, "최신 편집 계획 버전을 사용해야 합니다.")
            if current.status.value != "approved":
                raise AppError(ErrorCode.INVALID_PLAN, "승인된 편집 계획만 렌더링할 수 있습니다.")
            approved = ApprovedEditPlan.model_validate(current.model_dump())
            project = self.get_project(project_id)
            videos = self._videos(project)
            self.plans.validate_clips(approved.clips, videos, project)
            transcripts = tuple(self.get_transcript(project.id, video.id) for video in videos)
            destination = self.store.output_path(project.id, approved)
            result = self.editor.render(videos, transcripts, approved, destination)
            if (result.project_id != project.id or result.plan_id != approved.id
                    or result.plan_version != approved.version
                    or result.used_clip_ids != tuple(c.id for c in approved.clips)
                    or result.renderer_version != self.editor.VERSION):
                raise AppError(ErrorCode.INVALID_REFERENCE, "렌더 결과가 승인 계획과 다릅니다.")
            if not result.output_path.is_file() or result.output_path.stat().st_size == 0:
                raise AppError(ErrorCode.OUTPUT_INVALID, "렌더 파일이 존재하지 않습니다.")
            self.store.save_render(result)
            return result

    def get_render_result(self, project_id: str) -> RenderResult:
        return self.store.render(project_id)

    def submit_prepare_video(self, project_id: str, video_id: str) -> JobStatus:
        self._require_video(project_id, video_id)
        return self.scheduler.submit(
            JobKind.PREPARE, project_id,
            lambda: self.prepare_video(project_id, video_id).id,
            video_id=video_id,
        )

    def submit_prepare(self, project_id: str) -> JobStatus:
        return self.scheduler.submit(JobKind.PREPARE, project_id, lambda: self.prepare_project(project_id).id)

    def submit_recommend(self, request: SearchRequest) -> JobStatus:
        return self.scheduler.submit(JobKind.RECOMMEND, request.project_id, lambda: self.recommend(request).id)

    def submit_render(self, project_id: str, plan_id: str, expected_version: int) -> JobStatus:
        return self.scheduler.submit(JobKind.RENDER, project_id,
                                     lambda: self.render(project_id, plan_id, expected_version).id)

    def get_job(self, job_id: str) -> JobStatus:
        return self.scheduler.get(job_id)

    def close(self) -> None:
        self.scheduler.shutdown()
        for component in (self.preprocessor, self.analyzer):
            close = getattr(component, "close", None)
            if callable(close):
                close()
