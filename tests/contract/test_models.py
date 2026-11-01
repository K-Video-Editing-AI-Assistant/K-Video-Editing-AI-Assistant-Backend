from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from video_assistant.core.models import (
    ApprovedEditPlan, ClipSelection, EditPlan, JobKind, JobState, JobStatus,
    PlanStatus, Transcript, TranscriptSegment, VideoAsset,
)


def test_video_roundtrip() -> None:
    video = VideoAsset(
        id="video-1", project_id="project-1", source_path=Path("runtime/source.mp4"),
        original_name="source.mp4", duration_ms=60_000, sha256="a" * 64,
        has_audio=True,
    )
    assert VideoAsset.model_validate_json(video.model_dump_json()) == video


def test_invalid_segment_range_rejected() -> None:
    with pytest.raises(ValidationError):
        TranscriptSegment(id="s1", start_ms=5_000, end_ms=4_000, text="bad")


def test_empty_transcript_is_valid() -> None:
    transcript = Transcript(
        id="t1", video_id="v1", language="ko", segments=(),
        transcriber_version="stub-1", is_stub=True,
    )
    assert transcript.segments == ()


def test_transcript_overlap_rejected() -> None:
    with pytest.raises(ValidationError):
        Transcript(
            id="t1", video_id="v1", language="ko", transcriber_version="v1",
            segments=(
                TranscriptSegment(id="s1", start_ms=1000, end_ms=3000, text="first"),
                TranscriptSegment(id="s2", start_ms=2500, end_ms=4000, text="second"),
            ),
        )


def test_draft_can_have_no_clips_but_approved_cannot() -> None:
    draft = EditPlan(
        id="plan1", video_id="v1", request_id="q1",
        recommendation_id="r1", version=1, clips=(),
    )
    assert draft.status == PlanStatus.DRAFT
    with pytest.raises(ValidationError):
        ApprovedEditPlan(
            id="plan1", video_id="v1", request_id="q1",
            recommendation_id="r1", version=1, clips=(),
            approved_at=datetime.now(timezone.utc),
        )


def test_approved_plan_roundtrip() -> None:
    plan = ApprovedEditPlan(
        id="plan1", video_id="v1", request_id="q1", recommendation_id="r1",
        version=2,
        clips=(ClipSelection(id="c1", start_ms=3000, end_ms=6000),),
        approved_at=datetime.now(timezone.utc),
    )
    assert ApprovedEditPlan.model_validate_json(plan.model_dump_json()) == plan
    assert plan.status == PlanStatus.APPROVED


def test_successful_job_requires_reference_and_finish_time() -> None:
    with pytest.raises(ValidationError):
        JobStatus(
            id="job1", kind=JobKind.RENDER, project_id="p1", video_id="v1",
            state=JobState.SUCCEEDED, progress=100,
        )


def test_invalid_numeric_string_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClipSelection(id="c1", start_ms="1000", end_ms=2000)
