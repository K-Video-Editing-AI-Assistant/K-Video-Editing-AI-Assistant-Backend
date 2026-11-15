"""Development doubles for upstream Whisper and downstream FFmpeg work."""

import shutil
from pathlib import Path

from core.errors import AppError, ErrorCode
from core.interfaces import Transcriber, VideoEditor
from core.models import (
    ApprovedEditPlan, RenderResult, Transcript, TranscriptSegment, VideoAsset, new_id,
)
from processing.files import probe_video


class StubTranscriber(Transcriber):
    """Return predictable fake speech; it does NOT listen to video audio."""

    VERSION = "stub-transcriber-v1"

    def transcribe(self, video: VideoAsset) -> Transcript:
        segments = ()
        if video.has_audio:
            midpoint = video.duration_ms // 2
            if midpoint > 0 and video.duration_ms - midpoint > 0:
                segments = (
                    TranscriptSegment(id=new_id(), start_ms=0, end_ms=midpoint,
                                      text="[테스트 자막] AI 기술은 반복 작업을 자동화합니다."),
                    TranscriptSegment(id=new_id(), start_ms=midpoint, end_ms=video.duration_ms,
                                      text="[테스트 자막] AI 활용은 생산성을 높일 수 있습니다."),
                )
        return Transcript(id=new_id(), video_id=video.id, segments=segments,
                          transcriber_version=self.VERSION, is_stub=True)


class StubVideoEditor(VideoEditor):
    """Copy the first source MP4. The approved clip list is NOT rendered."""

    VERSION = "stub-editor-v1"

    def render(
        self, videos: tuple[VideoAsset, ...], transcripts: tuple[Transcript, ...],
        plan: ApprovedEditPlan, output_path: Path,
    ) -> RenderResult:
        if not videos or not plan.clips:
            raise AppError(ErrorCode.INVALID_PLAN, "편집에 필요한 영상과 클립이 없습니다.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(videos[0].source_path, output_path)
        duration, _ = probe_video(output_path)
        return RenderResult(
            id=new_id(), project_id=plan.project_id, plan_id=plan.id,
            plan_version=plan.version, output_path=output_path, duration_ms=duration,
            used_clip_ids=tuple(clip.id for clip in plan.clips),
            renderer_version=self.VERSION, is_stub=True,
        )
