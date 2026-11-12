import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai.providers.gemini import GeminiProcessingError, GeminiTranscriptRefiner
from core.models import ProcessedSegment


def segments(count):
    return tuple(
        ProcessedSegment(
            id=f"segment-{index}", start_ms=index * 1000,
            end_ms=(index + 1) * 1000, text=f"비공개 테스트 문장 {index}",
            source_segment_ids=(f"source-{index}",),
        )
        for index in range(count)
    )


def test_logs_batch_count_and_completion_without_transcript_text(caplog):
    data = segments(17)
    def generate(**kwargs):
        payload = json.loads(kwargs["contents"].split("교정 대상:\n", 1)[1])
        return SimpleNamespace(text=json.dumps(payload, ensure_ascii=False))
    client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=generate)))
    refiner = GeminiTranscriptRefiner("secret-test-key", "test-model", client)
    with caplog.at_level(logging.INFO):
        result = refiner.refine(data)
    assert result == tuple(item.text for item in data)
    assert client.models.generate_content.call_count == 2
    assert "자막 17개, 배치 2개, 동시 요청 수 1" in caplog.text
    assert "배치 1/2 완료" in caplog.text
    assert "배치 2/2 완료" in caplog.text
    assert "전체 완료" in caplog.text
    assert "비공개 테스트 문장" not in caplog.text
    assert "secret-test-key" not in caplog.text


def test_failed_batch_stops_processing_and_does_not_log_exception_details(caplog):
    client = SimpleNamespace(models=SimpleNamespace(
        generate_content=Mock(side_effect=RuntimeError("secret exception detail")),
    ))
    refiner = GeminiTranscriptRefiner(None, "test-model", client)
    with caplog.at_level(logging.INFO), pytest.raises(GeminiProcessingError):
        refiner.refine(segments(33))
    assert client.models.generate_content.call_count == 1
    assert "배치 1/3 실패" in caplog.text
    assert "전체 완료" not in caplog.text
    assert "secret exception detail" not in caplog.text


def test_empty_input_does_not_call_api(caplog):
    client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock()))
    refiner = GeminiTranscriptRefiner(None, "test-model", client)
    with caplog.at_level(logging.INFO):
        assert refiner.refine(()) == ()
    client.models.generate_content.assert_not_called()
    assert "배치 0개" in caplog.text
