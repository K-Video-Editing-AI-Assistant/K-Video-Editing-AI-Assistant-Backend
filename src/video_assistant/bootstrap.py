"""Composition root: choose stub/real adapter independently per module."""

from __future__ import annotations

from .analysis.stub import StubContentAnalyzer
from .analysis.simple import SimpleAIAnalyzer
from .core.config import Settings
from .core.errors import AppError, ErrorCode
from .core.jobs import ThreadJobScheduler
from .core.plan_service import DefaultPlanService
from .core.storage import FileProjectStore
from .core.workflow import DefaultApplicationService
from .editing.stub import StubVideoEditor
from .recommendation.stub import StubSegmentRecommender
from .recommendation.keyword import KeywordSegmentRecommender
from .transcription.stub import StubTranscriber


# After implementing a real adapter, import its class and add it to the
# matching registry. No other module needs to import that concrete class.
TRANSCRIBERS = {"stub": StubTranscriber}
ANALYZERS = {"stub": StubContentAnalyzer, "simple": SimpleAIAnalyzer}
RECOMMENDERS = {"stub": StubSegmentRecommender, "keyword": KeywordSegmentRecommender}
EDITORS = {"stub": StubVideoEditor}


def _make(choices: dict, name: str, kind: str):
    factory = choices.get(name)
    if factory is None:
        raise AppError(ErrorCode.INVALID_INPUT, f"{kind} 구현 '{name}'은 아직 등록되지 않았습니다.")
    return factory()


def create_application(settings: Settings | None = None) -> DefaultApplicationService:
    settings = settings or Settings.from_env()
    settings.validate()
    transcriber = _make(TRANSCRIBERS, settings.transcriber_backend, "음성 인식")
    analyzer = _make(ANALYZERS, settings.analyzer_backend, "분석")
    recommender = _make(RECOMMENDERS, settings.recommender_backend, "추천")
    editor = _make(EDITORS, settings.editor_backend, "영상 편집")
    store = FileProjectStore(settings.runtime_dir)
    store.recover_interrupted_jobs()
    scheduler = ThreadJobScheduler(store, max_workers=1)
    return DefaultApplicationService(
        store=store, plans=DefaultPlanService(store), scheduler=scheduler,
        transcriber=transcriber, analyzer=analyzer,
        recommender=recommender, editor=editor,
        runtime_dir=settings.runtime_dir, max_upload_mb=settings.max_upload_mb,
    )
