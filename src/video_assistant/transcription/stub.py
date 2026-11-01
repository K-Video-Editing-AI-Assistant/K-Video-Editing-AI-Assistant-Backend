"""Synthetic transcript; does not recognize audio."""

from uuid import uuid4

from video_assistant.core.interfaces import Transcriber
from video_assistant.core.models import Transcript, TranscriptSegment, VideoAsset


class StubTranscriber(Transcriber):
    VERSION = "stub-transcriber-v1"

    def transcribe(self, video: VideoAsset) -> Transcript:
        if not video.has_audio:
            segments = ()
        else:
            samples = (
                "[데모] 영상의 첫 번째 주제를 소개합니다.",
                "[데모] AI 활용 사례를 설명합니다.",
                "[데모] AI 활용의 장점과 마무리를 설명합니다.",
            )
            count = min(3, video.duration_ms)
            segments = tuple(
                TranscriptSegment(
                    id=uuid4().hex, start_ms=i * video.duration_ms // count,
                    end_ms=(i + 1) * video.duration_ms // count, text=samples[i],
                ) for i in range(count)
            )
        return Transcript(
            id=uuid4().hex, video_id=video.id, language="ko" if segments else "und",
            segments=segments, transcriber_version=self.VERSION, is_stub=True,
        )
