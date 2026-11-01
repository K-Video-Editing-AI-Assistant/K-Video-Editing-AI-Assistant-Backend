"""Demonstrate how RecommendationResult travels through application/store to EditPlan."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from uuid import uuid4

from video_assistant.bootstrap import create_application
from video_assistant.core.config import Settings
from video_assistant.core.models import JobState, SearchRequest


def finish(app, job_id: str):
    deadline = monotonic() + 20
    while monotonic() < deadline:
        status = app.get_job(job_id)
        if status.state in (JobState.SUCCEEDED, JobState.FAILED):
            if status.state == JobState.FAILED:
                raise RuntimeError(f"{status.error_code}: {status.error_message}")
            return status
        sleep(0.05)
    raise TimeoutError(f"작업이 종료되지 않았습니다: {job_id}")


def main() -> None:
    video_path = Path(__file__).resolve().parents[1] / "examples" / "demo.mp4"
    with TemporaryDirectory(prefix="video-assistant-guide-") as tmp:
        app = create_application(Settings(runtime_dir=Path(tmp), recommender_backend="keyword"))
        try:
            with video_path.open("rb") as source:
                video = app.ingest("demo.mp4", source)

            prepare_job = app.submit_prepare(video.id)
            finish(app, prepare_job.id)
            transcript = app.get_transcript(video.id)
            analysis = app.get_analysis(video.id)
            assert transcript is not None and analysis is not None

            request = SearchRequest(
                id=uuid4().hex, video_id=video.id, query="AI 활용", max_clips=2,
            )
            recommend_job = app.submit_recommend(request)
            completed = finish(app, recommend_job.id)
            assert completed.result_ref is not None

            result = app.get_recommendation(completed.result_ref)
            print("[1] 반환된 RecommendationResult (저장된 객체의 JSON 표현)")
            print(result.model_dump_json(indent=2))
            print(f"[2] JobStatus.result_ref == RecommendationResult.id: {completed.result_ref == result.id}")
            print(f"[3] Transcript.id == RecommendationResult.transcript_id: {transcript.id == result.transcript_id}")
            print(f"[4] VideoAnalysis.id == RecommendationResult.analysis_id: {analysis.id == result.analysis_id}")

            plan = app.create_plan(result.id)
            print(f"[5] EditPlan.recommendation_id == RecommendationResult.id: {plan.recommendation_id == result.id}")
            print(f"[6] EditPlan.version={plan.version}, status={plan.status.value}, clips={len(plan.clips)}")
            assert plan.recommendation_id == result.id
        finally:
            app.scheduler.shutdown()


if __name__ == "__main__":
    main()
