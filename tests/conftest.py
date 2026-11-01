from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep

import pytest

from video_assistant.bootstrap import create_application
from video_assistant.core.config import Settings
from video_assistant.core.models import JobState

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo.mp4"


@pytest.fixture
def service(tmp_path):
    app = create_application(Settings(runtime_dir=tmp_path))
    try:
        yield app
    finally:
        app.scheduler.shutdown()


@pytest.fixture
def video(service):
    with DEMO.open("rb") as handle:
        return service.ingest("demo.mp4", handle)


def finish(app, job):
    deadline = monotonic() + 12
    while monotonic() < deadline:
        status = app.get_job(job.id)
        if status.state in (JobState.SUCCEEDED, JobState.FAILED):
            return status
        sleep(0.04)
    raise TimeoutError("Job did not complete")
