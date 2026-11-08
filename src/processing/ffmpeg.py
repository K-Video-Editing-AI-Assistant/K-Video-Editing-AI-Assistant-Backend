"""Video-processing owner: baseline multi-source FFmpeg clip trimming and concatenation.

Unlike StubVideoEditor, this module actually cuts the approved source ranges.
Subtitle burning and fancy transitions are NOT implemented in this skeleton.
"""

import subprocess
import tempfile
from pathlib import Path

from core.errors import AppError, ErrorCode
from core.interfaces import VideoEditor
from core.models import ApprovedEditPlan, RenderResult, Transcript, VideoAsset, new_id
from processing.files import probe_video


class FFmpegVideoEditor(VideoEditor):
    VERSION = "ffmpeg-editor-baseline-v1"

    def render(
        self, videos: tuple[VideoAsset, ...], transcripts: tuple[Transcript, ...],
        plan: ApprovedEditPlan, output_path: Path,
    ) -> RenderResult:
        """Re-encode approved clips to a uniform MP4 and concatenate in plan order."""
        by_id = {video.id: video for video in videos}
        if not plan.clips or any(clip.video_id not in by_id for clip in plan.clips):
            raise AppError(ErrorCode.INVALID_PLAN, "편집 계획의 원본 영상이 없습니다.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="clipnote-render-") as tmp:
            folder = Path(tmp)
            pieces = []
            for index, clip in enumerate(plan.clips):
                video = by_id[clip.video_id]
                if clip.end_ms > video.duration_ms:
                    raise AppError(ErrorCode.INVALID_PLAN, "클립 시간이 원본 영상을 초과합니다.")
                duration = (clip.end_ms - clip.start_ms) / 1000
                piece = folder / f"piece_{index:04d}.mp4"
                cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{clip.start_ms / 1000:.3f}", "-i", str(video.source_path),
                ]
                if not video.has_audio:
                    cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
                cmd.extend(["-t", f"{duration:.3f}", "-map", "0:v:0",
                            "-map", "0:a:0" if video.has_audio else "1:a:0",
                            "-vf", "scale=640:360:force_original_aspect_ratio=decrease,"
                                   "pad=640:360:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                            "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(piece)])
                self._run(cmd)
                if not piece.exists() or piece.stat().st_size == 0:
                    raise AppError(ErrorCode.OUTPUT_INVALID, "추출 클립 파일이 생성되지 않았습니다.")
                pieces.append(piece)
            manifest = folder / "concat.txt"
            manifest.write_text("".join(f"file '{p.name}'\n" for p in pieces), encoding="utf-8")
            self._run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "0", "-i", str(manifest),
                "-c", "copy", "-movflags", "+faststart", str(output_path),
            ])
        duration_ms, _ = probe_video(output_path)
        return RenderResult(
            id=new_id(), project_id=plan.project_id, plan_id=plan.id,
            plan_version=plan.version, output_path=output_path, duration_ms=duration_ms,
            used_clip_ids=tuple(clip.id for clip in plan.clips),
            renderer_version=self.VERSION, is_stub=False,
        )

    @staticmethod
    def _run(args: list[str]) -> None:
        """Do not invoke a shell or execute LLM-generated commands."""
        try:
            subprocess.run(args, capture_output=True, text=True, check=True, timeout=300)
        except (OSError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise AppError(ErrorCode.RENDER_FAILED, f"FFmpeg 실행 실패: {detail[-500:]}") from exc
