"""AI-01 자막 전처리: 규칙 기반 정규화 + 선택적 Gemini 문장 교정.

공개 계약은 TranscriptPreprocessor.preprocess(Transcript) -> ProcessedTranscript입니다.
Gemini가 교정할 수 있는 필드는 자막 텍스트뿐입니다. ID·타임스탬프·원본 참조는
Python 코드가 생성·보존합니다. API 실패 시 기본적으로 전체 결과를 규칙 기반으로
되돌리고, preprocessing_version에 사용한 경로를 기록합니다.
"""

import logging
import re
import unicodedata
from typing import Any

from core.errors import AppError, ErrorCode
from core.interfaces import TranscriptPreprocessor
from core.models import (
    ProcessedSegment, ProcessedTranscript, Transcript, TranscriptSegment, new_id,
)

from ai.config import AIFallbackPolicy, AIProvider, AISettings
from ai.providers.gemini import GeminiProcessingError, GeminiTranscriptRefiner


logger = logging.getLogger(__name__)


class AITranscriptPreprocessor(TranscriptPreprocessor):
    """기존 Core 인터페이스를 바꾸지 않고 AI 제공자를 선택합니다."""

    VERSION = "rule-based-preprocessor-v1"
    GEMINI_VERSION = "gemini-preprocessor-v1"
    FALLBACK_VERSION = "rule-based-preprocessor-v1:gemini-fallback"
    _END_MARKS = (".", "!", "?", "。", "！", "？", "…")

    def __init__(
        self, max_gap_ms: int = 300, max_chars: int = 180, merge_adjacent: bool = True,
        settings: AISettings | None = None, gemini_client: Any | None = None,
    ):
        """기본값은 Gemini + 규칙 기반 fallback. 테스트에서는 설정과 클라이언트를 주입할 수 있습니다."""
        if type(max_gap_ms) is not int or max_gap_ms < 0:
            raise ValueError("max_gap_ms must be a non-negative integer")
        if type(max_chars) is not int or max_chars < 1:
            raise ValueError("max_chars must be a positive integer")
        if not isinstance(merge_adjacent, bool):
            raise ValueError("merge_adjacent must be a boolean")
        if settings is not None and not isinstance(settings, AISettings):
            raise ValueError("settings must be AISettings")

        self.max_gap_ms = max_gap_ms
        self.max_chars = max_chars
        self.merge_adjacent = merge_adjacent
        self.settings = settings if settings is not None else AISettings.from_env()
        self.gemini_client = gemini_client

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFC", text)
        return re.sub(r"\s+", " ", normalized).strip()

    def _can_merge(self, previous: ProcessedSegment, current: TranscriptSegment, text: str) -> bool:
        if not self.merge_adjacent:
            return False
        if current.start_ms < previous.end_ms:
            return False  # 겹치는 발언(다른 화자일 수 있음)은 합치지 않습니다.
        if current.start_ms - previous.end_ms > self.max_gap_ms:
            return False
        if len(previous.text) + 1 + len(text) > self.max_chars:
            return False

        tail = previous.text.rstrip(" \"'”’)]}")
        return not tail.endswith(self._END_MARKS)

    def _rule_based(self, transcript: Transcript) -> ProcessedTranscript:
        processed: list[ProcessedSegment] = []
        for segment in transcript.segments:
            text = self._normalize_text(segment.text)
            if not text:
                continue

            if processed and self._can_merge(processed[-1], segment, text):
                previous = processed.pop()
                processed.append(ProcessedSegment(
                    id=previous.id,
                    start_ms=previous.start_ms,
                    end_ms=segment.end_ms,
                    text=f"{previous.text} {text}",
                    source_segment_ids=(*previous.source_segment_ids, segment.id),
                ))
            else:
                processed.append(ProcessedSegment(
                    id=new_id(),
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=text,
                    source_segment_ids=(segment.id,),
                ))

        return ProcessedTranscript(
            id=new_id(),
            video_id=transcript.video_id,
            source_transcript_id=transcript.id,
            segments=tuple(processed),
            preprocessing_version=self.VERSION,
            is_stub=False,
        )

    def preprocess(self, transcript: Transcript) -> ProcessedTranscript:
        """원본 발언 근거와 시간 좌표를 보존하는 ProcessedTranscript를 반환합니다."""
        if not isinstance(transcript, Transcript):
            raise AppError(ErrorCode.INVALID_INPUT, "Transcript 객체가 필요합니다.")

        baseline = self._rule_based(transcript)
        provider = self.settings.provider
        if provider == AIProvider.RULE_BASED or not baseline.segments:
            return baseline
        if provider != AIProvider.GEMINI:
            raise AppError(ErrorCode.INVALID_INPUT, f"AI 제공자 '{provider.value}'는 아직 구현되지 않았습니다.")

        refiner = GeminiTranscriptRefiner(
            api_key=self.settings.gemini_api_key,
            model=self.settings.gemini_model,
            client=self.gemini_client,
        )
        try:
            corrected_texts = refiner.refine(baseline.segments)
        except GeminiProcessingError as exc:
            cause = exc.__cause__
            code = getattr(cause, "code", None)
            # SDK 상세 메시지에는 요청 데이터가 포함될 수 있어 유형/숫자 코드만 기록합니다.
            logger.error(
                "Gemini 자막 전처리 실패 — 모델 %s, 원인 %s, HTTP 코드 %s, 구분 %s",
                self.settings.gemini_model,
                type(cause).__name__ if cause is not None else type(exc).__name__,
                code if isinstance(code, int) else "unknown",
                "api_request" if str(exc) == "Gemini API 호출에 실패했습니다." else "response_validation",
            )
            if self.settings.fallback == AIFallbackPolicy.RULE_BASED:
                # API 키·자막 원문·서비스 응답을 로그에 남기지 않습니다.
                logger.warning("Gemini 전처리 실패로 규칙 기반 결과를 반환합니다 (%s).", type(exc).__name__)
                return baseline.model_copy(update={"preprocessing_version": self.FALLBACK_VERSION})
            raise AppError(ErrorCode.ANALYSIS_FAILED, "Gemini 자막 전처리에 실패했습니다.", retryable=True) from exc

        corrected = tuple(
            ProcessedSegment(
                id=segment.id,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=text,
                source_segment_ids=segment.source_segment_ids,
            )
            for segment, text in zip(baseline.segments, corrected_texts, strict=True)
        )
        return ProcessedTranscript(
            id=baseline.id,
            video_id=baseline.video_id,
            source_transcript_id=baseline.source_transcript_id,
            segments=corrected,
            preprocessing_version=f"{self.GEMINI_VERSION}:{self.settings.gemini_model}",
            is_stub=False,
        )


class RuleBasedTranscriptPreprocessor(AITranscriptPreprocessor):
    """로컬 규칙만 사용하며 다른 AI 모듈의 제공자 설정을 변경하지 않습니다."""

    def __init__(self):
        super().__init__(settings=AISettings(provider=AIProvider.RULE_BASED))
