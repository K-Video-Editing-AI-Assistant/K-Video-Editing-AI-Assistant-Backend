"""Whisper owner entrypoint (not implemented in the skeleton).

Implement Transcriber.transcribe(VideoAsset)->Transcript. The actual model can be
any Whisper variant; keep timestamp units in integer milliseconds.
Test independently before adding it to application/bootstrap.py.
"""

from core.interfaces import Transcriber
from core.models import Transcript, VideoAsset


class WhisperTranscriber(Transcriber):
    VERSION = "whisper-unimplemented"

    def transcribe(self, video: VideoAsset) -> Transcript:
        raise NotImplementedError("Whisper 담당자가 구현해야 합니다.")
