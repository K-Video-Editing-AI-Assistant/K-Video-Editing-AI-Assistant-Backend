"""Draft/revision/approval semantics independent of Streamlit."""

from __future__ import annotations

from uuid import uuid4

from .errors import AppError, ErrorCode
from .interfaces import PlanService, ProjectStore
from .models import (
    ApprovedEditPlan, ClipSelection, EditPlan, PlanStatus, utc_now,
)


class DefaultPlanService(PlanService):
    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def _check_clips(self, video_id: str, transcript_id: str, clips: tuple[ClipSelection, ...]) -> None:
        video = self.store.get_video(video_id)
        transcript = self.store.get_transcript(transcript_id)
        known_segments = {segment.id for segment in transcript.segments}
        for clip in clips:
            if clip.end_ms > video.duration_ms:
                raise AppError(ErrorCode.INVALID_PLAN, "추천/편집 구간이 영상 길이를 초과합니다.")
            if not set(clip.source_segment_ids).issubset(known_segments):
                raise AppError(ErrorCode.INVALID_PLAN, "자막에 존재하지 않는 구간 참조가 있습니다.")

    def create_draft(self, recommendation_id: str) -> EditPlan:
        result = self.store.get_recommendation(recommendation_id)
        self._check_clips(result.video_id, result.transcript_id, result.clips)
        plan = EditPlan(
            id=uuid4().hex, video_id=result.video_id, request_id=result.request_id,
            recommendation_id=result.id, version=1, clips=result.clips,
        )
        self.store.save_plan(plan, expected_version=None, expected_status=None)
        return plan

    def revise(self, plan_id: str, expected_version: int, clips: tuple[ClipSelection, ...]) -> EditPlan:
        plan = self.store.get_plan(plan_id)
        if plan.status != PlanStatus.DRAFT or plan.version != expected_version:
            raise AppError(ErrorCode.PLAN_CONFLICT, "최신 초안만 수정할 수 있습니다.")
        result = self.store.get_recommendation(plan.recommendation_id)
        try:
            updated = EditPlan.model_validate({
                **plan.model_dump(), "version": plan.version + 1, "clips": clips,
            })
        except ValueError as exc:
            raise AppError(ErrorCode.INVALID_PLAN, "수정한 구간 데이터가 올바르지 않습니다.") from exc
        self._check_clips(plan.video_id, result.transcript_id, updated.clips)
        self.store.save_plan(updated, expected_version=expected_version, expected_status=PlanStatus.DRAFT)
        return updated

    def approve(self, plan_id: str, expected_version: int) -> ApprovedEditPlan:
        plan = self.store.get_plan(plan_id)
        if plan.version != expected_version or plan.status != PlanStatus.DRAFT:
            raise AppError(ErrorCode.PLAN_CONFLICT, "최신 초안만 승인할 수 있습니다.")
        if not plan.clips:
            raise AppError(ErrorCode.INVALID_PLAN, "구간이 없는 계획은 승인할 수 없습니다.")
        result = self.store.get_recommendation(plan.recommendation_id)
        self._check_clips(plan.video_id, result.transcript_id, plan.clips)
        approved = ApprovedEditPlan.model_validate({
            **plan.model_dump(), "status": PlanStatus.APPROVED, "approved_at": utc_now(),
        })
        self.store.save_plan(approved, expected_version=expected_version, expected_status=PlanStatus.DRAFT)
        return approved

    def get_plan(self, plan_id: str, version: int | None = None) -> EditPlan:
        return self.store.get_plan(plan_id, version)
