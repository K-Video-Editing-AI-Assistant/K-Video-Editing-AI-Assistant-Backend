"""Media probing: validate actual MP4 streams with ffprobe."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .errors import AppError, ErrorCode


def probe_mp4(path: Path) -> tuple[int, bool]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not any(item.get("codec_type") == "video" for item in streams):
            raise ValueError("Video stream not found")
        duration_ms = round(float(data["format"]["duration"]) * 1000)
        if duration_ms <= 0:
            raise ValueError("Invalid duration")
        return duration_ms, any(item.get("codec_type") == "audio" for item in streams)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise AppError(ErrorCode.INVALID_INPUT, "MP4 파일을 FFprobe로 확인할 수 없습니다.") from exc
