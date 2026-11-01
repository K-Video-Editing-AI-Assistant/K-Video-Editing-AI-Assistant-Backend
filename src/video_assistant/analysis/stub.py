"""Synthetic analysis generated from the supplied transcript."""

from uuid import uuid4

from video_assistant.core.interfaces import ContentAnalyzer
from video_assistant.core.models import TopicSection, Transcript, VideoAnalysis


class StubContentAnalyzer(ContentAnalyzer):
    VERSION = "stub-analyzer-v1"

    def analyze(self, transcript: Transcript) -> VideoAnalysis:
        topics = tuple(
            TopicSection(
                id=uuid4().hex, title=f"[데모] 주제 {i + 1}",
                start_ms=seg.start_ms, end_ms=seg.end_ms, segment_ids=(seg.id,),
            ) for i, seg in enumerate(transcript.segments)
        )
        return VideoAnalysis(
            id=uuid4().hex, video_id=transcript.video_id, transcript_id=transcript.id,
            summary="[데모] 자막 기반 가상 영상 요약입니다." if topics else "",
            topics=topics, analyzer_version=self.VERSION, is_stub=True,
        )
