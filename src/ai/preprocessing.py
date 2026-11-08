"""AI 담당자: TranscriptPreprocessor의 실제 구현 위치.

독립 Fixture로 먼저 preprocess()를 테스트하고 전체 앱에 등록하세요.
원본 Transcript는 변경하지 않고 source_segment_ids를 유지해야 합니다.
"""

from core.interfaces import TranscriptPreprocessor
from core.models import ProcessedTranscript, Transcript


class AITranscriptPreprocessor(TranscriptPreprocessor):
    VERSION = "preprocessor-unimplemented"

    def preprocess(self, transcript: Transcript) -> ProcessedTranscript:
        raise NotImplementedError("AI 자막 전처리 담당자가 구현해야 합니다.")
