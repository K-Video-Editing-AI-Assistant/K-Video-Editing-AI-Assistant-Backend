"""담당 모듈이 반드시 구현해야 하는 공개 인터페이스(ABC).

이 파일은 실제 Whisper/LLM/FFmpeg 코드를 담지 않습니다.
각 담당자는 자신의 폴더에서 아래 추상 클래스를 상속하고 메서드를 구현합니다.
Application 계층(ApplicationService)은 추상 타입만 사용해 Stub/실제 구현을 교체합니다.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from .models import (
    ApprovedEditPlan, ProcessedTranscript, Project, ProjectAnalysis,
    RecommendationResult, RenderResult, SearchRequest, Transcript,
    VideoAnalysis, VideoAsset,
)


class Transcriber(ABC):
    """영상처리 담당: 하나의 원본 영상에서 발언과 시간 정보를 추출합니다."""

    @abstractmethod
    def transcribe(self, video: VideoAsset) -> Transcript:
        """입력: 원본 영상. 출력: 같은 video.id를 참조하는 Transcript.

        무음이면 segments=()를 반환합니다. 음성 인식 자체가 실패하면 오류를 발생시킵니다.
        """
        raise NotImplementedError


class TranscriptPreprocessor(ABC):
    """AI 영상분석 담당: 원본 자막을 검색·분석에 적합하게 정리합니다."""

    @abstractmethod
    def preprocess(self, transcript: Transcript) -> ProcessedTranscript:
        """전처리 결과는 source_transcript_id와 원본 자막 ID 참조를 유지합니다."""
        raise NotImplementedError


class ContentAnalyzer(ABC):
    """AI 영상분석 담당: 영상 하나의 전체 요약과 주제 구간을 만듭니다."""

    @abstractmethod
    def analyze(self, transcript: ProcessedTranscript) -> VideoAnalysis:
        """분석 결과는 원본/전처리 Transcript ID를 함께 보존해야 합니다."""
        raise NotImplementedError


class ProjectAnalyzer(ABC):
    """AI 영상분석 담당: 여러 영상 분석의 공통 주제·검색 키워드를 정리합니다."""

    @abstractmethod
    def analyze_project(
        self, project: Project, analyses: tuple[VideoAnalysis, ...]
    ) -> ProjectAnalysis:
        """기존 영상 분석 결과를 조합하며, 사용자 자연어 요청에는 종속되지 않습니다."""
        raise NotImplementedError


class SegmentRecommender(ABC):
    """AI 영상분석 담당: 사용자 요청에 맞는 다중 영상 구간을 선택합니다."""

    @property
    def result_versions(self) -> tuple[str, ...]:
        """이 구현체가 반환할 수 있는 결과 버전 (폴백 포함)."""
        return (self.VERSION,)

    @abstractmethod
    def recommend(
        self,
        request: SearchRequest,
        transcripts: tuple[Transcript, ...],
        analyses: tuple[VideoAnalysis, ...],
        project_analysis: ProjectAnalysis,
    ) -> RecommendationResult:
        """출력 클립마다 video_id와 원본 자막 ID를 포함합니다.

        반환된 clips의 순서가 추천 재생 순서입니다. 일치하는 구간이 없다면
        clips=(), topics=()인 RecommendationResult를 반환합니다.
        """
        raise NotImplementedError


class VideoEditor(ABC):
    """영상처리 담당: 승인 계획을 실제 MP4로 만듭니다."""

    @abstractmethod
    def render(
        self,
        videos: tuple[VideoAsset, ...],
        transcripts: tuple[Transcript, ...],
        plan: ApprovedEditPlan,
        output_path: Path,
    ) -> RenderResult:
        """videos에서 PlanClip.video_id의 원본을 찾아 잘라 붙입니다.

        자막을 입히는 경우 원본 Transcript의 시간을 출력 시간으로 재배치합니다.
        출력 파일을 검증한 후 RenderResult를 반환합니다.
        """
        raise NotImplementedError
