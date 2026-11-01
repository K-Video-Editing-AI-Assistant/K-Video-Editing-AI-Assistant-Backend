"""Stub output copies the original MP4, NEVER applies the edit plan."""

import os
import shutil
from pathlib import Path
from uuid import uuid4

from video_assistant.core.errors import AppError, ErrorCode
from video_assistant.core.interfaces import VideoEditor
from video_assistant.core.media import probe_mp4
from video_assistant.core.models import ApprovedEditPlan, RenderResult, VideoAsset


class StubVideoEditor(VideoEditor):
    VERSION = "stub-editor-original-copy-v1"

    def render(self, video: VideoAsset, plan: ApprovedEditPlan, output_path: Path) -> RenderResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(f".{uuid4().hex}.mp4")
        try:
            shutil.copyfile(video.source_path, temporary)
            duration_ms, _ = probe_mp4(temporary)
            os.replace(temporary, output_path)
        except (OSError, AppError) as exc:
            raise AppError(ErrorCode.RENDER_FAILED, "Stub 결과 영상을 복사하지 못했습니다.") from exc
        finally:
            temporary.unlink(missing_ok=True)
        return RenderResult(
            id=uuid4().hex, video_id=video.id, plan_id=plan.id,
            plan_version=plan.version, output_path=output_path,
            duration_ms=duration_ms, renderer_version=self.VERSION, is_stub=True,
        )
