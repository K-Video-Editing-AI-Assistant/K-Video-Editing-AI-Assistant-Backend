from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from video_assistant.core.errors import AppError, ErrorCode
from video_assistant.core.models import JobKind, JobState, JobStatus, PlanStatus
from video_assistant.core.storage import FileProjectStore


def test_restart_marks_orphaned_jobs_failed(tmp_path):
    store = FileProjectStore(tmp_path)
    queued = JobStatus(id=uuid4().hex, kind=JobKind.PREPARE, project_id="project", video_id="video")
    store.create_job(queued)
    store.recover_interrupted_jobs()
    restored = store.get_job(queued.id)
    assert restored.state == JobState.FAILED
    assert restored.error_code == ErrorCode.WORKER_FAILED.value
    assert restored.finished_at is not None


def test_invalid_id_does_not_escape_storage_path(tmp_path):
    store = FileProjectStore(tmp_path)
    with pytest.raises(AppError):
        store.get_job("../../secret")


def test_unregistered_real_backend_fails_fast(tmp_path):
    from video_assistant.bootstrap import create_application
    from video_assistant.core.config import Settings

    with pytest.raises(AppError) as err:
        create_application(Settings(runtime_dir=tmp_path, editor_backend="ffmpeg"))
    assert err.value.code == ErrorCode.INVALID_INPUT
