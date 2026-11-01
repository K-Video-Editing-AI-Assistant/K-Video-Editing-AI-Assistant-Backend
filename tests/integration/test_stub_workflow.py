from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest

from video_assistant.core.errors import AppError, ErrorCode
from video_assistant.core.models import ClipSelection, JobState, PlanStatus, SearchRequest
from tests.conftest import DEMO, finish


def prepared(service, video):
    status = finish(service, service.submit_prepare(video.id))
    assert status.state == JobState.SUCCEEDED, status.error_message
    return service.get_transcript(video.id), service.get_analysis(video.id)


def recommend(service, video, query="AI 활용", max_clips=3):
    req = SearchRequest(id=uuid4().hex, video_id=video.id, query=query, max_clips=max_clips)
    status = finish(service, service.submit_recommend(req))
    assert status.state == JobState.SUCCEEDED, status.error_message
    return service.get_recommendation(status.result_ref)


def test_stub_end_to_end_with_plan_revision_and_actual_mp4(service, video):
    transcript, analysis = prepared(service, video)
    assert transcript.video_id == analysis.video_id == video.id
    result = recommend(service, video)
    assert len(result.clips) == 3
    plan = service.create_plan(result.id)
    assert plan.status == PlanStatus.DRAFT
    with pytest.raises(AppError) as err:
        service.submit_render(plan.id, plan.version)
    assert err.value.code == ErrorCode.PLAN_CONFLICT
    reversed_clips = tuple(reversed(plan.clips))
    revised = service.revise_plan(plan.id, plan.version, reversed_clips)
    assert revised.version == 2 and revised.clips == reversed_clips
    approved = service.approve_plan(plan.id, revised.version)
    assert approved.status == PlanStatus.APPROVED and approved.version == 2
    status = finish(service, service.submit_render(approved.id, approved.version))
    assert status.state == JobState.SUCCEEDED, status.error_message
    output = service.get_render_result(status.result_ref)
    assert output.is_stub and output.plan_version == 2
    assert output.output_path.is_file()
    assert output.output_path.read_bytes() == video.source_path.read_bytes()


def test_prepare_reuses_cached_transcript_and_analysis(service, video):
    initial = prepared(service, video)
    subsequent = prepared(service, video)
    assert (initial[0].id, initial[1].id) == (subsequent[0].id, subsequent[1].id)


def test_no_result_is_valid_but_cannot_be_approved(service, video):
    prepared(service, video)
    result = recommend(service, video, query="추천 없음")
    assert result.clips == ()
    plan = service.create_plan(result.id)
    with pytest.raises(AppError) as err:
        service.approve_plan(plan.id, plan.version)
    assert err.value.code == ErrorCode.INVALID_PLAN


def test_stale_revision_and_approval_are_rejected(service, video):
    prepared(service, video)
    result = recommend(service, video)
    plan = service.create_plan(result.id)
    revised = service.revise_plan(plan.id, plan.version, plan.clips)
    with pytest.raises(AppError) as err:
        service.revise_plan(plan.id, plan.version, plan.clips)
    assert err.value.code == ErrorCode.PLAN_CONFLICT
    service.approve_plan(plan.id, revised.version)
    with pytest.raises(AppError):
        service.revise_plan(plan.id, revised.version, revised.clips)


def test_out_of_range_edit_is_rejected(service, video):
    prepared(service, video)
    plan = service.create_plan(recommend(service, video).id)
    clipped = ClipSelection(id=uuid4().hex, start_ms=100, end_ms=video.duration_ms + 100)
    with pytest.raises(AppError) as err:
        service.revise_plan(plan.id, plan.version, (clipped,))
    assert err.value.code == ErrorCode.INVALID_PLAN


def test_bad_upload_rejected(service):
    with pytest.raises(AppError) as err:
        service.ingest("fake.mp4", BytesIO(b"not an mp4"))
    assert err.value.code == ErrorCode.INVALID_INPUT


def test_renderer_does_not_fabricate_cut_video(service, video):
    prepared(service, video)
    plan = service.create_plan(recommend(service, video, max_clips=1).id)
    approved = service.approve_plan(plan.id, plan.version)
    job = finish(service, service.submit_render(approved.id, approved.version))
    output = service.get_render_result(job.result_ref)
    assert output.duration_ms == video.duration_ms  # Whole input copy, not selection duration
