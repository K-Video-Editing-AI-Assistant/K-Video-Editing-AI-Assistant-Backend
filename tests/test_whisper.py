"""WhisperTranscriber 독립 테스트.

기본 테스트는 실제 모델 없이 돌아갑니다. faster-whisper와 ffmpeg가 설치돼 있으면
examples/demo.mp4로 실제 인식 테스트도 실행합니다.
"""

import hashlib
import importlib.util
import shutil
import sys
import wave
from pathlib import Path
import pytest

from core.errors import AppError, ErrorCode
from core.models import VideoAsset
from processing.whisper import WhisperTranscriber

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo.mp4"


def make_video(tmp_path: Path, has_audio: bool = True, duration_ms: int = 10_000) -> VideoAsset:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake")
    return VideoAsset(
        id="v1", project_id="p1", filename="a.mp4", source_path=source,
        duration_ms=duration_ms, sha256="0" * 64, has_audio=has_audio,
    )


def fake_model(transcriber, monkeypatch, raw):
    monkeypatch.setattr(transcriber, "_extract_audio", lambda *args, **kwargs: None)
    monkeypatch.setattr(transcriber, "_run_model", lambda wav: raw)


def write_wav(path: Path, frames: bytes) -> Path:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16000)
        writer.writeframes(frames)
    return path


def test_no_audio_returns_empty_transcript(tmp_path):
    result = WhisperTranscriber(model_size="tiny").transcribe(make_video(tmp_path, has_audio=False))
    assert result.segments == ()
    assert result.video_id == "v1"
    assert result.is_stub is False


def test_silence_returns_empty_transcript(tmp_path, monkeypatch):
    transcriber = WhisperTranscriber(model_size="tiny")
    fake_model(transcriber, monkeypatch, [])
    assert transcriber.transcribe(make_video(tmp_path)).segments == ()


def test_converts_and_cleans_segments(tmp_path, monkeypatch):
    transcriber = WhisperTranscriber(model_size="tiny")
    fake_model(transcriber, monkeypatch, [
        (2.0, 3.5, "  둘째 "),      
        (0.0, 1.25, "첫째"),        
        (4.0, 4.0, "길이0"),         
        (5.0, 6.0, "   "),          
        (9.5, 12.0, "끝 초과"),     
    ])
    result = transcriber.transcribe(make_video(tmp_path))
    assert [(s.start_ms, s.end_ms, s.text) for s in result.segments] == [
        (0, 1250, "첫째"), (2000, 3500, "둘째"), (9500, 10000, "끝 초과"),
    ]
    assert result.transcriber_version == transcriber.VERSION


def test_missing_source_file(tmp_path):
    video = make_video(tmp_path)
    Path(video.source_path).unlink()
    with pytest.raises(AppError) as info:
        WhisperTranscriber(model_size="tiny").transcribe(video)
    assert info.value.code == ErrorCode.NOT_FOUND


def test_missing_library_gives_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)  
    monkeypatch.setattr(WhisperTranscriber, "_model_cache", {})
    with pytest.raises(AppError) as info:
        WhisperTranscriber(model_size="tiny")._load_model()
    assert info.value.code == ErrorCode.TRANSCRIPTION_FAILED


def test_load_wav_reads_16bit_mono(tmp_path):
    path = write_wav(tmp_path / "a.wav", b"\x00\x40" * 16000)
    audio = WhisperTranscriber._load_wav(path)
    assert audio.shape == (16000,)
    assert abs(float(audio[0]) - 0.5) < 1e-6


def test_empty_wav_is_silence(tmp_path, monkeypatch):
    path = write_wav(tmp_path / "empty.wav", b"")
    transcriber = WhisperTranscriber(model_size="tiny")
    monkeypatch.setattr(transcriber, "_load_model", lambda: pytest.fail("모델을 불러오면 안 됨"))
    assert transcriber._run_model(path) == []


def test_version_reflects_model_settings():
    assert WhisperTranscriber(model_size="tiny").VERSION != WhisperTranscriber(model_size="small").VERSION


@pytest.mark.skipif(
    importlib.util.find_spec("faster_whisper") is None or shutil.which("ffmpeg") is None
    or not DEMO.exists(),
    reason="faster-whisper / ffmpeg / demo.mp4 중 하나가 없음",
)
def test_real_demo_video():
    from processing.files import probe_video

    duration_ms, has_audio = probe_video(DEMO)
    video = VideoAsset(
        id="demo", project_id="p1", filename="demo.mp4", source_path=DEMO,
        duration_ms=duration_ms, sha256=hashlib.sha256(DEMO.read_bytes()).hexdigest(),
        has_audio=has_audio,
    )
    result = WhisperTranscriber(model_size="tiny").transcribe(video)
    for segment in result.segments:
        assert 0 <= segment.start_ms < segment.end_ms <= duration_ms

def test_segment_progress_is_logged(tmp_path, monkeypatch, caplog):
    import logging
    from types import SimpleNamespace

    transcriber = WhisperTranscriber(model_size="tiny")
    model = SimpleNamespace(transcribe=lambda *args, **kwargs: (
        iter([SimpleNamespace(start=0.0, end=1.5, text="test speech")]), None,
    ))
    monkeypatch.setattr(transcriber, "_load_model", lambda: model)
    with caplog.at_level(logging.INFO, logger="processing.whisper"):
        result = transcriber._run_model(write_wav(tmp_path / "audio.wav", b"\x00\x40" * 16000))
    assert result == [(0.0, 1.5, "test speech")]
    assert "Whisper 모델 로드 완료" in caplog.text
    assert "자막 인식 중: 0.0~1.5초" in caplog.text
    assert "자막 인식 완료" in caplog.text
    assert "test speech" not in caplog.text
