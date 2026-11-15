"""Component composition point. Register each finished implementation here.

Step 1: Implement and test a module independently with shared fixtures.
Step 2: Add its factory to the corresponding registry below.
Step 3: Select the registry key in .env and run the full Stub/Real workflow.
The FastAPI entry point and the legacy Streamlit test UI reuse this factory.
"""

from ai.stub import (
    StubContentAnalyzer, StubPreprocessor, StubProjectAnalyzer, StubSegmentRecommender,
)
from application.config import Settings
from application.jobs import JobScheduler, JobStore
from application.service import ApplicationService
from application.storage import ProjectStore
from core.errors import AppError, ErrorCode
from processing.ffmpeg import FFmpegVideoEditor
from processing.stub import StubTranscriber, StubVideoEditor
from processing.whisper import WhisperTranscriber
from ai.analyzer import LLMContentAnalyzer
from ai.recommender import LLMSegmentRecommender
from ai.preprocessing import AITranscriptPreprocessor, RuleBasedTranscriptPreprocessor

# After developing a real implementation, import it here and add a key.
TRANSCRIBERS = {
    "stub": StubTranscriber, 
    "whisper": WhisperTranscriber
}
PREPROCESSORS = {
    "stub": StubPreprocessor,
    "rule_based": RuleBasedTranscriptPreprocessor,
    "ai": AITranscriptPreprocessor,
}
ANALYZERS = {
    "stub": StubContentAnalyzer,
    "llm": LLMContentAnalyzer,
}
PROJECT_ANALYZERS = {"stub": StubProjectAnalyzer}
RECOMMENDERS = {"stub": StubSegmentRecommender, "llm": LLMSegmentRecommender}
EDITORS = {"stub": StubVideoEditor, "ffmpeg": FFmpegVideoEditor}


def _make(registry: dict, selected: str, kind: str):
    """Construct a module through its registered no-argument class/factory."""
    factory = registry.get(selected)
    if factory is None:
        raise AppError(ErrorCode.INVALID_INPUT, f"{kind} 구현체 '{selected}'은 아직 등록되지 않았습니다.")
    return factory()


def create_application(settings: Settings | None = None) -> ApplicationService:
    """Create the ApplicationService used by FastAPI, the test UI and tests."""
    settings = settings or Settings.from_env()
    return ApplicationService(
        store=ProjectStore(settings.runtime_dir),
        scheduler=JobScheduler(JobStore(settings.runtime_dir)),
        transcriber=_make(TRANSCRIBERS, settings.transcriber_backend, "음성 인식"),
        preprocessor=_make(PREPROCESSORS, settings.preprocessor_backend, "자막 전처리"),
        analyzer=_make(ANALYZERS, settings.analyzer_backend, "영상 분석"),
        project_analyzer=_make(PROJECT_ANALYZERS, settings.project_analyzer_backend, "프로젝트 분석"),
        recommender=_make(RECOMMENDERS, settings.recommender_backend, "구간 추천"),
        editor=_make(EDITORS, settings.editor_backend, "영상 편집"),
    )
