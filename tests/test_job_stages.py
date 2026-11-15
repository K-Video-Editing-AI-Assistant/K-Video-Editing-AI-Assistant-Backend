from threading import Event

import pytest

from application.jobs import JobScheduler, JobStore
from core.models import JobKind, JobState


@pytest.mark.parametrize('fail', [False, True])
def test_stage_is_visible_while_running_and_preserved_on_failure(tmp_path, fail):
    scheduler = JobScheduler(JobStore(tmp_path))
    reached, release = Event(), Event()
    def run():
        scheduler.report_stage('transcribing')
        reached.set()
        assert release.wait(5)
        scheduler.report_stage('analyzing')
        if fail:
            raise RuntimeError('analysis failed')
        return 'result-id'
    try:
        job = scheduler.submit(JobKind.PREPARE, 'project', run, video_id='video')
        assert reached.wait(5)
        running = scheduler.get(job.id)
        assert running.state == JobState.RUNNING
        assert running.stage == 'transcribing'
        assert running.video_id == 'video'
        release.set()
        scheduler.futures[job.id].result(timeout=5)
        finished = scheduler.get(job.id)
        assert finished.stage == ('analyzing' if fail else 'completed')
        assert finished.state == (JobState.FAILED if fail else JobState.SUCCEEDED)
    finally:
        release.set()
        scheduler.shutdown()
