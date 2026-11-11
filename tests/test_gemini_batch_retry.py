import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from ai.config import AISettings, AIFallbackPolicy
from ai.preprocessing import AITranscriptPreprocessor
from ai.providers.gemini import GeminiProcessingError, GeminiTranscriptRefiner
from core.errors import AppError
from core.models import ProcessedSegment, Transcript, TranscriptSegment


def segment():
    return ProcessedSegment(id='s', start_ms=0, end_ms=1000, text='원문', source_segment_ids=('s',))


def response():
    return SimpleNamespace(text=json.dumps({'segments': [{'id': 's', 'text': '원문'}]}))


def api_error(code):
    error = RuntimeError('secret server response')
    error.code = code
    return error


def refiner_with(outcomes, retries=2):
    call = Mock(side_effect=outcomes)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=call))
    return GeminiTranscriptRefiner(None, 'test', client, max_retries=retries), call


@pytest.mark.parametrize('code', [408, 429, 500, 502, 503, 504])
def test_transient_error_retries_only_failed_request(monkeypatch, code):
    sleep = Mock()
    monkeypatch.setattr('ai.providers.gemini.sleep', sleep)
    monkeypatch.setattr('ai.providers.gemini.uniform', lambda a, b: 0)
    refiner, call = refiner_with([api_error(code), api_error(code), response()])
    assert refiner.refine((segment(),)) == ('원문',)
    assert call.call_count == 3
    assert [args.args[0] for args in sleep.call_args_list] == [1, 2]


@pytest.mark.parametrize('code', [400, 401, 403, 404])
def test_permanent_error_is_not_retried(monkeypatch, code):
    sleep = Mock()
    monkeypatch.setattr('ai.providers.gemini.sleep', sleep)
    refiner, call = refiner_with([api_error(code)])
    with pytest.raises(GeminiProcessingError) as caught:
        refiner.refine((segment(),))
    assert caught.value.retryable is False
    assert call.call_count == 1
    sleep.assert_not_called()


def test_retry_limit_and_safe_logs(monkeypatch, caplog):
    monkeypatch.setattr('ai.providers.gemini.sleep', lambda seconds: None)
    refiner, call = refiner_with([api_error(429)] * 3)
    with pytest.raises(GeminiProcessingError) as caught:
        refiner.refine((segment(),))
    assert caught.value.retryable is True
    assert call.call_count == 3
    assert 'secret server response' not in caplog.text
    assert '전체 완료' not in caplog.text


@pytest.mark.parametrize('error', [httpx.ReadTimeout('timeout'), httpx.ConnectError('connection')])
def test_transport_error_is_retried(monkeypatch, error):
    monkeypatch.setattr('ai.providers.gemini.sleep', lambda seconds: None)
    refiner, call = refiner_with([error, response()])
    assert refiner.refine((segment(),)) == ('원문',)
    assert call.call_count == 2


def test_invalid_response_is_not_retried():
    refiner, call = refiner_with([SimpleNamespace(text='not json')])
    with pytest.raises(GeminiProcessingError) as caught:
        refiner.refine((segment(),))
    assert caught.value.retryable is False
    assert call.call_count == 1


def test_zero_retries_disables_retry():
    refiner, call = refiner_with([api_error(503)], retries=0)
    with pytest.raises(GeminiProcessingError):
        refiner.refine((segment(),))
    assert call.call_count == 1


@pytest.mark.parametrize('value', [-1, 6, True, 1.5])
def test_invalid_retry_setting(value):
    with pytest.raises(ValueError):
        AISettings(preprocessing_max_retries=value)
    with pytest.raises(ValueError):
        GeminiTranscriptRefiner(None, 'test', SimpleNamespace(), max_retries=value)


def test_sdk_retries_are_disabled(monkeypatch):
    from google import genai
    factory = Mock()
    monkeypatch.setattr(genai, 'Client', factory)
    GeminiTranscriptRefiner('test-key', 'test')
    assert factory.call_args.kwargs['http_options']['retry_options']['attempts'] == 1


def test_retry_config_reads_zero_from_environment(monkeypatch):
    monkeypatch.setenv('PREPROCESSING_MAX_RETRIES', '0')
    assert AISettings.from_env().preprocessing_max_retries == 0


@pytest.mark.parametrize('policy', [AIFallbackPolicy.RAISE, AIFallbackPolicy.RULE_BASED])
def test_preprocessor_handles_exhausted_retries_without_partial_result(monkeypatch, policy):
    monkeypatch.setattr('ai.providers.gemini.sleep', lambda seconds: None)
    call = Mock(side_effect=[api_error(503)] * 3)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=call))
    preprocessor = AITranscriptPreprocessor(
        settings=AISettings(fallback=policy, preprocessing_concurrency=2),
        gemini_client=client,
    )
    transcript = Transcript(id='t', video_id='v', transcriber_version='test', segments=(
        TranscriptSegment(id='s', start_ms=0, end_ms=1000, text='원문'),
    ))
    if policy == AIFallbackPolicy.RAISE:
        with pytest.raises(AppError) as caught:
            preprocessor.preprocess(transcript)
        assert caught.value.retryable is True
    else:
        result = preprocessor.preprocess(transcript)
        assert result.segments[0].text == '원문'
        assert 'fallback' in result.preprocessing_version
    assert call.call_count == 3
