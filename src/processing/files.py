"""Video-processing owner: actual MP4 file intake, probing and subtitle exports.

Metadata JSON and project relationships live in application/storage.py.
This module handles file bytes, never domain workflow or approval.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

from core.errors import AppError, ErrorCode
from core.models import Transcript, VideoAsset, new_id

MAX_UPLOAD_SIZE = 250 * 1024 * 1024


def probe_video(path: Path) -> tuple[int, bool]:
    """Return positive duration in milliseconds and whether an audio stream exists."""
    import json
    try:
        process = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
             "-of", "json", str(path)], capture_output=True, text=True,
            check=True, timeout=30,
        )
        data = json.loads(process.stdout)
        streams = data.get("streams", ())
        if not any(item.get("codec_type") == "video" for item in streams):
            raise ValueError("영상 스트림이 없습니다.")
        duration = round(float(data["format"]["duration"]) * 1000)
        if duration <= 0:
            raise ValueError("영상 길이가 유효하지 않습니다.")
        return duration, any(item.get("codec_type") == "audio" for item in streams)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise AppError(ErrorCode.INVALID_INPUT, f"MP4/FFprobe 검사 실패: {exc}") from exc


def validate_upload(filename: str, contents: bytes) -> None:
    if not filename or Path(filename).name != filename or "\\" in filename:
        raise AppError(ErrorCode.INVALID_INPUT, "파일 이름이 유효하지 않습니다.")
    if not filename.lower().endswith(".mp4"):
        raise AppError(ErrorCode.UNSUPPORTED_FILE_TYPE, "MP4 파일만 허용합니다.")
    if len(contents) > MAX_UPLOAD_SIZE:
        raise AppError(ErrorCode.UPLOAD_TOO_LARGE, "250MB 제한을 초과했습니다.")
    if not contents:
        raise AppError(ErrorCode.INVALID_INPUT, "빈 파일은 업로드할 수 없습니다.")


def save_upload(project_id: str, filename: str, contents: bytes, root: Path) -> VideoAsset:
    """Persist one MP4 inside the project and return its immutable VideoAsset."""
    validate_upload(filename, contents)
    video_id = new_id()
    directory = root / "projects" / project_id / "videos" / video_id
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "source.mp4"
    try:
        path.write_bytes(contents)
        duration, has_audio = probe_video(path)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return VideoAsset(
        id=video_id, project_id=project_id, filename=filename, source_path=path,
        duration_ms=duration, sha256=hashlib.sha256(contents).hexdigest(), has_audio=has_audio,
    )


def write_srt(transcript: Transcript, path: Path) -> Path:
    """Automatically save speech segments as a human-readable SRT file."""
    def timestamp(ms: int) -> str:
        hours, leftover = divmod(ms, 3_600_000)
        minutes, leftover = divmod(leftover, 60_000)
        seconds, fraction = divmod(leftover, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{fraction:03d}"

    lines = []
    for index, segment in enumerate(transcript.segments, start=1):
        lines.append(f"{index}\n{timestamp(segment.start_ms)} --> {timestamp(segment.end_ms)}\n{segment.text}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
