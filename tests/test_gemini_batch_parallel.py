from threading import Barrier, Event, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai.config import AISettings
from ai.providers.gemini import GeminiProcessingError, GeminiTranscriptRefiner
from core.models import ProcessedSegment


def make_segments(count):
    return tuple(ProcessedSegment(
        id=str(i), start_ms=i * 1000, end_ms=(i + 1) * 1000,
        text=f"자막 {i}", source_segment_ids=(str(i),),
    ) for i in range(count))


def test_parallel_execution_is_bounded_and_preserves_input_order(monkeypatch):
    refiner = GeminiTranscriptRefiner(None, 'test', SimpleNamespace(), max_concurrency=2)
    data = make_segments(33)
    barrier, release_first, lock = Barrier(2), Event(), Lock()
    active, peak, completed = 0, 0, []
    def refine_batch(batch):
        nonlocal active, peak
        index = int(batch[0].id) // 16
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            if index < 2:
                barrier.wait(timeout=5)
            if index == 0:
                assert release_first.wait(5)
            if index == 2:
                release_first.set()
            with lock:
                completed.append(index)
            return tuple(item.text for item in batch)
        finally:
            with lock:
                active -= 1
    monkeypatch.setattr(refiner, '_refine_batch', refine_batch)
    assert refiner.refine(data) == tuple(item.text for item in data)
    assert peak == 2
    assert completed.index(1) < completed.index(0)


def test_parallel_failure_returns_no_partial_success(monkeypatch):
    refiner = GeminiTranscriptRefiner(None, 'test', SimpleNamespace(), max_concurrency=2)
    calls = []
    def fail(batch):
        calls.append(batch[0].id)
        raise GeminiProcessingError('failed')
    monkeypatch.setattr(refiner, '_refine_batch', fail)
    with pytest.raises(GeminiProcessingError):
        refiner.refine(make_segments(65))
    assert len(calls) <= 2


@pytest.mark.parametrize('value', [0, 9, -1, True, 1.5, '3'])
def test_invalid_concurrency(value):
    with pytest.raises(ValueError):
        GeminiTranscriptRefiner(None, 'test', SimpleNamespace(), max_concurrency=value)
    with pytest.raises(ValueError):
        AISettings(preprocessing_concurrency=value)


def test_concurrency_reads_os_before_env_file(monkeypatch):
    monkeypatch.setattr('ai.config.dotenv_values', lambda path: {'PREPROCESSING_CONCURRENCY': '2'})
    monkeypatch.setenv('PREPROCESSING_CONCURRENCY', '4')
    assert AISettings.from_env().preprocessing_concurrency == 4
    monkeypatch.delenv('PREPROCESSING_CONCURRENCY')
    assert AISettings.from_env().preprocessing_concurrency == 2


def test_preprocessor_passes_concurrency_and_preserves_fallback(monkeypatch):
    from ai.config import AIFallbackPolicy
    from ai.preprocessing import AITranscriptPreprocessor
    from core.models import Transcript, TranscriptSegment
    factory = Mock()
    factory.return_value.refine.side_effect = GeminiProcessingError('failed batch')
    monkeypatch.setattr('ai.preprocessing.GeminiTranscriptRefiner', factory)
    transcript = Transcript(id='t', video_id='v', transcriber_version='test', segments=(
        TranscriptSegment(id='s', start_ms=0, end_ms=1000, text='원문'),
    ))
    preprocessor = AITranscriptPreprocessor(settings=AISettings(
        preprocessing_concurrency=2, fallback=AIFallbackPolicy.RULE_BASED,
    ))
    processed = preprocessor.preprocess(transcript)
    assert factory.call_args.kwargs['max_concurrency'] == 2
    assert processed.segments[0].text == '원문'
    assert 'fallback' in processed.preprocessing_version
