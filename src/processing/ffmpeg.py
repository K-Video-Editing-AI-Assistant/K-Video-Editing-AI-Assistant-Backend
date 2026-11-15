"""영상처리 담당: 승인된 구간을 잘라 이어 붙이고 자막을 합성합니다.

자막은 계획에 사용자 편집 자막(plan.subtitles)이 있으면 우선 사용하고, 없으면 Whisper 자막을 사용합니다.
설정: SUBTITLE_FONT, SUBTITLE_FONTS_DIR (.env)
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

from core.errors import AppError, ErrorCode
from core.interfaces import VideoEditor
from core.models import (
    ApprovedEditPlan, PlanClip, PlanSubtitle, RenderResult, SubtitleStyle, Transcript,
    VideoAsset, new_id,
)
from processing.files import probe_video

WIDTH, HEIGHT = 640, 360

SubtitleEvent = tuple[int, int, str]

_STYLES = {
    SubtitleStyle.BASIC: dict(size=20, bold=0, border=1, outline=1.5, text_color="&H00FFFFFF",
                              outline_color="&H00000000", back_color="&H00000000"),
    SubtitleStyle.BOLD: dict(size=26, bold=-1, border=1, outline=2.5, text_color="&H00FFFFFF",
                             outline_color="&H00000000", back_color="&H00000000"),
    SubtitleStyle.BOX: dict(size=20, bold=0, border=3, outline=5, text_color="&H00000000",
                            outline_color="&H00FFFFFF", back_color="&H00FFFFFF"),
}


def subtitle_events(clip: PlanClip, transcript: Transcript | None) -> list[SubtitleEvent]:
    if transcript is None:
        return []
    return _slice(((s.start_ms, s.end_ms, s.text) for s in transcript.segments),
                  clip.start_ms, clip.end_ms)


def edited_subtitle_events(
    clips: tuple[PlanClip, ...], subtitles: tuple[PlanSubtitle, ...],
) -> list[list[SubtitleEvent]]:
    result = []
    offset = 0
    for clip in clips:
        length = clip.end_ms - clip.start_ms
        result.append(_slice(((s.start_ms, s.end_ms, s.text) for s in subtitles),
                             offset, offset + length))
        offset += length
    return result


def _slice(items, start_ms: int, end_ms: int) -> list[SubtitleEvent]:
    events = []
    for item_start, item_end, text in items:
        start = max(item_start, start_ms)
        end = min(item_end, end_ms)
        if start < end:
            events.append((start - start_ms, end - start_ms, text))
    return events


def build_ass(events: list[SubtitleEvent], style: SubtitleStyle, font: str) -> str:
    s = _STYLES[style]
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {WIDTH}",
        f"PlayResY: {HEIGHT}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
        f"Style: Default,{font},{s['size']},{s['text_color']},{s['outline_color']},{s['back_color']},"
        f"{s['bold']},{s['border']},{s['outline']},0,2,20,20,18",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for start, end, text in events:
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{_ass_text(text)}")
    return "\n".join(lines) + "\n"


def _ass_time(ms: int) -> str:
    cs = ms // 10
    hours, cs = divmod(cs, 360_000)
    minutes, cs = divmod(cs, 6_000)
    seconds, cs = divmod(cs, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"


def _ass_text(text: str) -> str:
    text = text.replace("\\", "＼").replace("{", "(").replace("}", ")")
    return " ".join(text.split())


def _setting(name: str) -> str | None:
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    return os.environ.get(name) or values.get(name) or None


def _default_font() -> str:
    return _setting("SUBTITLE_FONT") or ("Malgun Gothic" if sys.platform == "win32" else "Noto Sans CJK KR")


def _default_fonts_dir() -> Path | None:
    configured = _setting("SUBTITLE_FONTS_DIR")
    if configured:
        return Path(configured)
    if sys.platform == "win32":
        folder = Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts"
        return folder if folder.is_dir() else None
    return None


def _filter_path(path: Path) -> str:
    return "'" + path.as_posix().replace(":", "\\:") + "'"


class FFmpegVideoEditor(VideoEditor):
    VERSION = "ffmpeg-editor-subtitle-v3"

    def __init__(self, font: str | None = None, fonts_dir: Path | None = None) -> None:
        self.font = font or _default_font()
        self.fonts_dir = fonts_dir if fonts_dir is not None else _default_fonts_dir()

    def render(
        self, videos: tuple[VideoAsset, ...], transcripts: tuple[Transcript, ...],
        plan: ApprovedEditPlan, output_path: Path,
    ) -> RenderResult:
        by_id = {video.id: video for video in videos}
        transcript_by_video = {t.video_id: t for t in transcripts if t is not None}
        if not plan.clips or any(clip.video_id not in by_id for clip in plan.clips):
            raise AppError(ErrorCode.INVALID_PLAN, "편집 계획의 원본 영상이 없습니다.")
        if plan.subtitles is not None:
            events_by_clip = edited_subtitle_events(plan.clips, plan.subtitles)
        else:
            events_by_clip = [
                subtitle_events(clip, transcript_by_video.get(clip.video_id)) for clip in plan.clips
            ]
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ai-video-assistant-render-") as tmp:
            folder = Path(tmp)
            pieces = []
            for index, clip in enumerate(plan.clips):
                video = by_id[clip.video_id]
                if clip.end_ms > video.duration_ms:
                    raise AppError(ErrorCode.INVALID_PLAN, "클립 시간이 원본 영상을 초과합니다.")
                video_filter = (
                    f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                    f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
                )
                events = events_by_clip[index]
                if events:
                    subtitle_name = f"sub_{index:04d}.ass"
                    (folder / subtitle_name).write_text(
                        build_ass(events, plan.subtitle_style, self.font), encoding="utf-8"
                    )
                    video_filter += f",ass={subtitle_name}"
                    if self.fonts_dir is not None:
                        video_filter += f":fontsdir={_filter_path(self.fonts_dir)}"

                duration = (clip.end_ms - clip.start_ms) / 1000
                piece = folder / f"piece_{index:04d}.mp4"
                cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{clip.start_ms / 1000:.3f}", "-i", str(Path(video.source_path).resolve()),
                ]
                if not video.has_audio:
                    cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
                cmd.extend(["-t", f"{duration:.3f}", "-map", "0:v:0",
                            "-map", "0:a:0" if video.has_audio else "1:a:0",
                            "-vf", video_filter,
                            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                            "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(piece)])
                self._run(cmd, folder)
                if not piece.exists() or piece.stat().st_size == 0:
                    raise AppError(ErrorCode.OUTPUT_INVALID, "추출 클립 파일이 생성되지 않았습니다.")
                pieces.append(piece)
            manifest = folder / "concat.txt"
            manifest.write_text("".join(f"file '{p.name}'\n" for p in pieces), encoding="utf-8")
            self._run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(manifest),
                "-c", "copy", "-movflags", "+faststart", str(output_path),
            ], folder)
        duration_ms, _ = probe_video(output_path)
        return RenderResult(
            id=new_id(), project_id=plan.project_id, plan_id=plan.id,
            plan_version=plan.version, output_path=output_path, duration_ms=duration_ms,
            used_clip_ids=tuple(clip.id for clip in plan.clips),
            renderer_version=self.VERSION, is_stub=False,
        )

    @staticmethod
    def _run(args: list[str], cwd: Path) -> None:
        """Do not invoke a shell or execute LLM-generated commands."""
        try:
            subprocess.run(args, capture_output=True, text=True, check=True, timeout=300, cwd=cwd)
        except (OSError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise AppError(ErrorCode.RENDER_FAILED, f"FFmpeg 실행 실패: {detail[-500:]}") from exc