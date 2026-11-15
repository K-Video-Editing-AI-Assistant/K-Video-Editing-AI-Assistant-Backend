from pathlib import Path

import pytest

from application.plans import PlanService
from core.errors import AppError, ErrorCode
from core.models import EditPlan, PlanClip, PlanSubtitle, Project, VideoAsset

PROJECT = Project(id="p1", title="t", video_ids=("v1",))
VIDEOS = (VideoAsset(
    id="v1", project_id="p1", filename="a.mp4", source_path=Path("a.mp4"),
    duration_ms=10_000, sha256="0" * 64, has_audio=True,
),)
CLIPS = (PlanClip(id="c0", video_id="v1", start_ms=0, end_ms=3000),)


def draft(**extra) -> EditPlan:
    return EditPlan(id="plan1", project_id="p1", recommendation_id="r1", version=1, clips=CLIPS, **extra)


def test_revise_sets_edited_subtitles():
    subtitles = (PlanSubtitle(start_ms=0, end_ms=1000, text="고친 자막"),)
    revised = PlanService().revise(draft(), 1, CLIPS, PROJECT, VIDEOS, subtitles)
    assert revised.subtitles == subtitles
    assert revised.version == 2


def test_revise_without_subtitles_keeps_previous():
    subtitles = (PlanSubtitle(start_ms=0, end_ms=1000, text="유지"),)
    revised = PlanService().revise(draft(subtitles=subtitles), 1, CLIPS, PROJECT, VIDEOS)
    assert revised.subtitles == subtitles


def test_revise_rejects_subtitle_outside_result():
    too_long = (PlanSubtitle(start_ms=2000, end_ms=4000, text="초과"),)
    with pytest.raises(AppError) as info:
        PlanService().revise(draft(), 1, CLIPS, PROJECT, VIDEOS, too_long)
    assert info.value.code == ErrorCode.INVALID_PLAN