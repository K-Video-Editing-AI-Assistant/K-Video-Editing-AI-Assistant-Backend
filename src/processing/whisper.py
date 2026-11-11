"""영상처리 담당: faster-whisper 기반 실제 음성 인식.

흐름: 원본 MP4 → (FFmpeg) 16kHz 모노 WAV → (faster-whisper) 세그먼트 → Transcript

계약(core/models.py) 규칙:
- 모든 시간은 원본 영상 기준 정수 ms이고 구간은 [start_ms, end_ms)입니다.
- segments는 시작 시간순으로 정렬합니다.
- 오디오가 없거나 말소리가 없으면 segments=()인 정상 Transcript를 반환합니다.

설정(.env 또는 OS 환경변수):
    WHISPER_MODEL=small         # tiny / base / small / medium / large-v3
    WHISPER_DEVICE=cpu          # cpu / cuda / auto
    WHISPER_COMPUTE_TYPE=int8   # CPU는 int8, GPU는 float16 권장
    WHISPER_LANGUAGE=ko
설치: pip install -e ".[test]"  (처음 실행 시 모델을 자동 다운로드)
"""

from __future__ import annotations

import os
import platform
import logging
from time import perf_counter

from dotenv import dotenv_values
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from core.errors import AppError, ErrorCode
from core.interfaces import Transcriber
from core.models import Transcript, TranscriptSegment, VideoAsset, new_id

if TYPE_CHECKING:  
    import numpy as np


logger = logging.getLogger(__name__)


RawSegment = tuple[float, float, str]


class WhisperTranscriber(Transcriber):

    IMPLEMENTATION = "faster-whisper-v1"
    VERSION = IMPLEMENTATION  

    _model_cache: dict[tuple[str, str, str], Any] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> None:
        values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
        def setting(name, default):
            return os.environ.get(name) or values.get(name) or default

        self.model_size = model_size or setting("WHISPER_MODEL", "small")
        requested_device = device or setting("WHISPER_DEVICE", "auto")
        self.device = requested_device
        if requested_device == "auto":
            self.device = "cpu"
            if platform.system() == "Darwin" and platform.machine().lower() in ("arm64", "aarch64"):
                try:
                    import ctranslate2
                    if ctranslate2.get_supported_compute_types("mps"):
                        self.device = "mps"
                except (ImportError, ValueError, RuntimeError):
                    logging.getLogger(__name__).warning("MPS를 사용할 수 없어 CPU를 사용합니다.")
        requested_compute = compute_type or setting("WHISPER_COMPUTE_TYPE", "auto")
        self.compute_type = requested_compute
        if requested_compute == "auto":
            self.compute_type = "int8" if self.device == "cpu" else "float32" if self.device == "mps" else "float16"
        self.language = language or setting("WHISPER_LANGUAGE", "ko")
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.VERSION = (
            f"{self.IMPLEMENTATION}:{self.model_size}:{self.compute_type}:{self.language}"
        )


    def transcribe(self, video: VideoAsset) -> Transcript:
        if not video.has_audio:
            return self._build(video, ())

        source = Path(video.source_path)
        if not source.exists():
            raise AppError(ErrorCode.NOT_FOUND, f"원본 영상 파일이 없습니다: {source.name}")

        with tempfile.TemporaryDirectory(prefix="clipnote-whisper-") as tmp:
            wav = Path(tmp) / "audio.wav"
            logger.info("오디오 추출 시작 — 영상 %.1f초", video.duration_ms / 1000)
            self._extract_audio(source, wav, video.duration_ms)
            logger.info("오디오 추출 완료")
            raw = self._run_model(wav)

        return self._build(video, self._to_segments(raw, video.duration_ms))


    def _build(self, video: VideoAsset, segments: tuple[TranscriptSegment, ...]) -> Transcript:
        return Transcript(
            id=new_id(), video_id=video.id, segments=segments, language=self.language,
            transcriber_version=self.VERSION, is_stub=False,
        )

    @staticmethod
    def _extract_audio(source: Path, wav: Path, duration_ms: int) -> None:
        """Whisper 입력용 16kHz 모노 WAV를 만듭니다. 셸을 거치지 않습니다."""
        timeout = 60 + duration_ms // 1000  # 영상 길이에 비례해 여유 있게
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", str(wav),
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise AppError(
                ErrorCode.TRANSCRIPTION_FAILED, f"오디오 추출 실패: {detail[-500:]}"
            ) from exc
        if not wav.exists() or wav.stat().st_size == 0:
            raise AppError(ErrorCode.TRANSCRIPTION_FAILED, "추출된 오디오 파일이 비어 있습니다.")

    def _load_model(self) -> Any:
        key = (self.model_size, self.device, self.compute_type)
        with self._cache_lock:
            if key not in self._model_cache:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise AppError(
                        ErrorCode.TRANSCRIPTION_FAILED,
                        'faster-whisper가 설치되지 않았습니다. pip install -e ".[test]"를 다시 실행하세요.',
                    ) from exc
                try:
                    self._model_cache[key] = WhisperModel(
                        self.model_size, device=self.device, compute_type=self.compute_type
                    )
                except Exception as exc:
                    raise AppError(
                        ErrorCode.TRANSCRIPTION_FAILED,
                        f"Whisper 모델 로드 실패({self.model_size}): {exc}",
                        retryable=True,
                    ) from exc
            return self._model_cache[key]

    @staticmethod
    def _load_wav(wav: Path) -> np.ndarray:
        import numpy as np

        try:
            with wave.open(str(wav), "rb") as reader:
                if reader.getsampwidth() != 2 or reader.getnchannels() != 1:
                    raise ValueError("16bit 모노 WAV가 아닙니다.")
                frames = reader.readframes(reader.getnframes())
        except (OSError, EOFError, wave.Error, ValueError) as exc:
            raise AppError(ErrorCode.TRANSCRIPTION_FAILED, f"오디오 파일을 읽을 수 없습니다: {exc}") from exc
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    def _run_model(self, wav: Path) -> list[RawSegment]:
        audio = self._load_wav(wav)
        if audio.size == 0:
            return []
        started = perf_counter()
        logger.info("Whisper 모델 로드 시작 — %s / %s / %s", self.model_size, self.device, self.compute_type)
        model = self._load_model()
        logger.info("Whisper 모델 로드 완료 — %.1f초", perf_counter() - started)
        started = perf_counter()
        logger.info("자막 인식 시작 — 첫 구간이 생성될 때까지 출력이 없을 수 있습니다")
        try:
            segments, _info = model.transcribe(
                audio, language=self.language, beam_size=self.beam_size,
                vad_filter=self.vad_filter,
            )
            result = []
            for seg in segments:
                result.append((seg.start, seg.end, seg.text))
                logger.info(
                    "자막 인식 중: %.1f~%.1f초 — %d개 구간, 경과 %.1f초",
                    seg.start, seg.end, len(result), perf_counter() - started,
                )
            logger.info("자막 인식 완료 — %d개 구간, %.1f초", len(result), perf_counter() - started)
            return result
        except Exception as exc:
            raise AppError(
                ErrorCode.TRANSCRIPTION_FAILED, f"음성 인식 실패: {exc}", retryable=True
            ) from exc

    @staticmethod
    def _to_segments(raw: Iterable[RawSegment], duration_ms: int) -> tuple[TranscriptSegment, ...]:
        """초 단위 결과를 계약 규칙(정수 ms, 영상 길이 안, 시작순 정렬)에 맞춥니다."""
        result: list[TranscriptSegment] = []
        for start_s, end_s, text in raw:
            text = (text or "").strip()
            if not text:
                continue
            start_ms = max(0, int(round(start_s * 1000)))
            end_ms = min(duration_ms, int(round(end_s * 1000)))
            if start_ms >= end_ms:  # 길이 0이거나 영상 끝을 넘어선 구간
                continue
            result.append(
                TranscriptSegment(id=new_id(), start_ms=start_ms, end_ms=end_ms, text=text)
            )
        result.sort(key=lambda segment: segment.start_ms)
        return tuple(result)