"""Network-free regression tests for adaptive parallel analysis."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from ai.analyzer import LLMContentAnalyzer
from ai.config import AIFallbackPolicy, AISettings
from ai.parallel_analysis import split_chunks
from core.errors import AppError
from core.models import ProcessedSegment, ProcessedTranscript


def transcript(count=8):
    return ProcessedTranscript(
        id="processed", video_id="video", source_transcript_id="raw",
        preprocessing_version="test",
        segments=tuple(
            ProcessedSegment(
                id=f"processed-{i}", start_ms=i * 1000, end_ms=(i + 1) * 1000,
                text=f"발언 {i}", source_segment_ids=(f"raw-{i}",),
            )
            for i in range(count)
        ),
    )


def settings(**kwargs):
    base = AISettings(
        gemini_api_key="fake", fallback=AIFallbackPolicy.RAISE,
        analysis_parallel_enabled=True, analysis_parallel_threshold=4,
        analysis_batch_segments=3, analysis_overlap_segments=1,
        analysis_concurrency=2,
    )
    return replace(base, **kwargs)


class FakeModels:
    def __init__(self, invalid=False):
        self.invalid = invalid
        self.calls = []

    def generate_content(self, *, model, contents, config):
        payload = json.loads(contents.split("입력 JSON:\n", 1)[1])
        if isinstance(payload, list):
            self.calls.append("reduce")
            ids = [entry["analysis"]["topics"][0]["processed_segment_ids"][0]
                   for entry in payload]
            output = {"summary": "반론과 결론을 포함한 전체 요약", "topics": [
                {"title": "통합 주제", "description": "설명", "processed_segment_ids": ids}
            ]}
        elif "target_segments" in payload:
            self.calls.append("map")
            ids = [payload["target_segments"][0]["id"]]
            if self.invalid:
                ids = ["99999"]
            output = {"summary": "부분 요약", "claims": [], "counterclaims": [],
                      "conclusions": [], "unresolved_references": [], "topics": [
                          {"title": "주제", "description": "설명", "processed_segment_ids": ids}
                      ]}
        else:
            self.calls.append("single")
            output = {"summary": "단일 분석", "topics": [
                {"title": "주제", "description": "", "processed_segment_ids": ["0"]}
            ]}
        return SimpleNamespace(text=json.dumps(output, ensure_ascii=False), usage_metadata=None)


def test_split_covers_each_core_once_and_preserves_overlap():
    chunks = split_chunks(transcript(), settings())
    assert [(c.start, c.end) for c in chunks] == [(0, 3), (3, 6), (6, 8)]
    assert [(c.context_start, c.context_end) for c in chunks] == [(0, 4), (2, 7), (5, 8)]


def test_parallel_maps_and_reduce_preserve_global_reference():
    models = FakeModels()
    analyzer = LLMContentAnalyzer(settings(), SimpleNamespace(models=models))
    result = analyzer.analyze(transcript())
    assert models.calls.count("map") == 3
    assert models.calls[-1] == "reduce"
    assert result.topics[0].source_segment_ids == ("raw-0", "raw-3", "raw-6")
    assert result.topics[0].start_ms == 0
    assert result.topics[0].end_ms == 7000
    assert result.analyzer_version == analyzer.cache_version


@pytest.mark.parametrize("enabled,count", [(False, 8), (True, 2)])
def test_single_path_preserved(enabled, count):
    models = FakeModels()
    analyzer = LLMContentAnalyzer(
        settings(analysis_parallel_enabled=enabled), SimpleNamespace(models=models),
    )
    assert analyzer.analyze(transcript(count)).summary == "단일 분석"
    assert models.calls == ["single"]


def test_invalid_map_reference_does_not_return_partial_success():
    models = FakeModels(invalid=True)
    analyzer = LLMContentAnalyzer(settings(), SimpleNamespace(models=models))
    with pytest.raises(AppError):
        analyzer.analyze(transcript())
    assert "reduce" not in models.calls


def test_cache_version_changes_when_parallel_enabled():
    assert LLMContentAnalyzer(settings()).cache_version != LLMContentAnalyzer(
        settings(analysis_parallel_enabled=False)
    ).cache_version
