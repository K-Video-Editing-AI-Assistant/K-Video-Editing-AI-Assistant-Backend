from unittest.mock import Mock

from ai.config import AIProvider
from ai.preprocessing import RuleBasedTranscriptPreprocessor
from application.config import Settings
from bootstrap import create_application


def test_local_preprocessing_keeps_analysis_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    service = create_application(Settings(
        runtime_dir=tmp_path, preprocessor_backend="rule_based", analyzer_backend="llm",
    ))
    try:
        assert isinstance(service.preprocessor, RuleBasedTranscriptPreprocessor)
        assert service.preprocessor.settings.provider == AIProvider.RULE_BASED
        assert service.analyzer.settings.provider == AIProvider.GEMINI
        monkeypatch.setattr("ai.preprocessing.GeminiTranscriptRefiner", Mock(side_effect=AssertionError("Gemini correction called")))
        from core.models import Transcript, TranscriptSegment, new_id
        transcript = Transcript(
            id=new_id(), video_id=new_id(), transcriber_version="test",
            segments=(TranscriptSegment(id=new_id(), start_ms=0, end_ms=1000, text="안녕하세요."),),
        )
        result = service.preprocessor.preprocess(transcript)
        assert result.segments[0].text == "안녕하세요."
        assert result.segments[0].source_segment_ids == (transcript.segments[0].id,)
        assert result.preprocessing_version == service.preprocessor.VERSION
        assert result.is_stub is False
    finally:
        service.close()
