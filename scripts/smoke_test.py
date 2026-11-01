"""Run the entire stub path without a Streamlit server."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from uuid import uuid4

from video_assistant.bootstrap import create_application
from video_assistant.core.config import Settings
from video_assistant.core.models import JobState, SearchRequest


ROOT = Path(__file__).resolve().parents[1]


def done(app, job):
    deadline = monotonic() + 15
    while monotonic() < deadline:
        status = app.get_job(job.id)
        if status.state in (JobState.SUCCEEDED, JobState.FAILED):
            if status.state == JobState.FAILED:
                raise RuntimeError(f"{status.error_code}: {status.error_message}")
            return status.result_ref
        sleep(0.04)
    raise TimeoutError("Smoke test job did not finish")


def main() -> None:
    with TemporaryDirectory() as temp:
        app = create_application(Settings(runtime_dir=Path(temp)))
        try:
            with (ROOT / "examples" / "demo.mp4").open("rb") as handle:
                video = app.ingest("demo.mp4", handle)
            done(app, app.submit_prepare(video.id))
            request = SearchRequest(id=uuid4().hex, video_id=video.id, query="AI 장점 정리")
            recommendation_id = done(app, app.submit_recommend(request))
            plan = app.create_plan(recommendation_id)
            approved = app.approve_plan(plan.id, plan.version)
            result_id = done(app, app.submit_render(approved.id, approved.version))
            result = app.get_render_result(result_id)
            print(f"PASS: output={result.output_path.name}, duration={result.duration_ms}ms, stub={result.is_stub}")
            print("WARNING: the stub editor copies the original video, not the selected clips.")
        finally:
            app.scheduler.shutdown()


if __name__ == "__main__":
    main()
