"""Small real implementation example: mark transcript segments mentioning AI."""

from uuid import uuid4

from video_assistant.core.interfaces import ContentAnalyzer
from video_assistant.core.models import TopicSection, Transcript, VideoAnalysis


class SimpleAIAnalyzer(ContentAnalyzer):
    VERSION = "simple-ai-analyzer-v1"

    def analyze(self, transcript: Transcript) -> VideoAnalysis:
        topics = []

        for segment in transcript.segments:
            if "ai" not in segment.text.casefold():
                continue

            topics.append(
                TopicSection(
                    id=uuid4().hex,
                    title="AI 관련 발언",
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    segment_ids=(segment.id,),
                )
            )

        return VideoAnalysis(
            id=uuid4().hex,
            video_id=transcript.video_id,
            transcript_id=transcript.id,
            summary=f"AI가 언급된 자막 구간은 {len(topics)}개입니다.",
            topics=tuple(topics),
            analyzer_version=self.VERSION,
            is_stub=False,
        )
