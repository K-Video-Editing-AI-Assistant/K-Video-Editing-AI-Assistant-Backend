"""AI 담당자: 영상별 요약과 프로젝트 단위 키워드 분석 구현 위치."""

from core.interfaces import ContentAnalyzer, ProjectAnalyzer
from core.models import ProcessedTranscript, Project, ProjectAnalysis, VideoAnalysis


class LLMContentAnalyzer(ContentAnalyzer):
    VERSION = "analyzer-unimplemented"

    def analyze(self, transcript: ProcessedTranscript) -> VideoAnalysis:
        raise NotImplementedError("AI 영상분석 담당자가 구현해야 합니다.")


class LLMProjectAnalyzer(ProjectAnalyzer):
    VERSION = "project-analyzer-unimplemented"

    def analyze_project(
        self, project: Project, analyses: tuple[VideoAnalysis, ...],
    ) -> ProjectAnalysis:
        raise NotImplementedError("AI 프로젝트 분석 담당자가 구현해야 합니다.")
