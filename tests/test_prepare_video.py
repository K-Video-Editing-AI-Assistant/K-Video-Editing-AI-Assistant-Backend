from unittest.mock import Mock

import pytest

from application.config import Settings
from bootstrap import create_application
from core.errors import AppError, ErrorCode
from core.models import Project, VideoAsset, new_id


def test_prepare_video_stores_results_without_project_analysis(tmp_path):
    service = create_application(Settings(runtime_dir=tmp_path))
    try:
        project = service.create_project()
        video_id = new_id()
        video = VideoAsset(
            id=video_id, project_id=project.id, filename="sample.mp4",
            source_path=service.store.video_dir(project.id, video_id) / "source.mp4",
            duration_ms=10000,
            sha256="0" * 64, has_audio=True,
        )
        service.store.save_video(video)
        video.source_path.touch()
        service.store.save_project(Project(
            id=project.id, title=project.title, video_ids=(video.id,),
        ))
        service.project_analyzer = Mock()
        service.transcriber.transcribe = Mock(wraps=service.transcriber.transcribe)

        analysis = service.prepare_video(project.id, video.id)
        transcript = service.get_transcript(project.id, video.id)
        processed = service.store.video_data(project.id, video.id, "processed")

        assert transcript.segments
        assert processed.source_transcript_id == transcript.id
        assert analysis.processed_transcript_id == processed.id
        assert analysis.transcript_id == transcript.id
        assert service.get_video_analysis(project.id, video.id) == analysis
        assert (service.store.video_dir(project.id, video.id) / "transcript.srt").is_file()
        assert service.prepare_video(project.id, video.id) == analysis
        service.transcriber.transcribe.assert_called_once_with(video)
        service.project_analyzer.analyze_project.assert_not_called()
    finally:
        service.close()


def test_prepare_video_rejects_video_outside_project(tmp_path):
    service = create_application(Settings(runtime_dir=tmp_path))
    try:
        project = service.create_project()
        service.transcriber.transcribe = Mock()
        with pytest.raises(AppError) as caught:
            service.prepare_video(project.id, "unrelated-video")
        assert caught.value.code == ErrorCode.INVALID_REFERENCE
        service.transcriber.transcribe.assert_not_called()
    finally:
        service.close()
