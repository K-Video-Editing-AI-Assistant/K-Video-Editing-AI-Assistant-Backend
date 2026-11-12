from unittest.mock import Mock

import pytest

from application.config import Settings
from bootstrap import create_application
from core.errors import AppError, ErrorCode
from core.models import Project, Transcript, TranscriptSegment, VideoAsset, new_id


@pytest.fixture
def stored_video(tmp_path):
    service = create_application(Settings(runtime_dir=tmp_path))
    project_id, video_id = new_id(), new_id()
    video = VideoAsset(
        id=video_id, project_id=project_id, filename="sample.mp4",
        source_path=service.store.video_dir(project_id, video_id) / "source.mp4", duration_ms=20000,
        sha256="0" * 64, has_audio=True,
    )
    service.store.save_project(Project(id=project_id, title="test", video_ids=(video_id,)))
    service.store.save_video(video)
    video.source_path.touch()
    service.transcriber.transcribe = Mock(side_effect=AssertionError("조회 중 음성 인식 실행"))
    service.preprocessor.preprocess = Mock(side_effect=AssertionError("조회 중 전처리 실행"))
    try:
        yield service, video
    finally:
        service.close()


@pytest.mark.parametrize("empty", [False, True])
def test_lookup_returns_saved_transcript_without_processing(stored_video, empty):
    service, video = stored_video
    transcript = Transcript(
        id=new_id(), video_id=video.id, transcriber_version="saved-version",
        segments=() if empty else (
            TranscriptSegment(id=new_id(), start_ms=12000, end_ms=18500, text="저장된 자막입니다."),
        ),
    )
    service.store.save_video_data(video.project_id, video.id, "transcript", transcript)

    assert service.get_transcript_by_video_id(video.id) == transcript
    service.transcriber.transcribe.assert_not_called()
    service.preprocessor.preprocess.assert_not_called()


@pytest.mark.parametrize("target,code", [
    ("invalid-id", ErrorCode.INVALID_INPUT),
    ("missing-video", ErrorCode.NOT_FOUND),
    ("missing-transcript", ErrorCode.NOT_FOUND),
])
def test_lookup_rejects_invalid_or_missing_resources(stored_video, target, code):
    service, video = stored_video
    video_id = video.id if target == "missing-transcript" else new_id() if target == "missing-video" else target
    with pytest.raises(AppError) as caught:
        service.get_transcript_by_video_id(video_id)
    assert caught.value.code == code
    service.transcriber.transcribe.assert_not_called()


def test_lookup_rejects_transcript_for_another_video(stored_video):
    service, video = stored_video
    transcript = Transcript(id=new_id(), video_id=new_id(), transcriber_version="test")
    service.store.save_video_data(video.project_id, video.id, "transcript", transcript)
    with pytest.raises(AppError) as caught:
        service.get_transcript_by_video_id(video.id)
    assert caught.value.code == ErrorCode.INVALID_REFERENCE
