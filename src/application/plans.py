"""Application 담당: draft revision, optimistic concurrency and approval rules."""

from core.errors import AppError, ErrorCode
from core.models import (
    ApprovedEditPlan, EditPlan, PlanClip, PlanStatus, Project,
    RecommendationResult, SubtitleStyle, VideoAsset, new_id, utc_now,
)


class PlanService:
    """Pure plan logic: does not read files or implement FFmpeg."""

    @staticmethod
    def validate_clips(clips: tuple[PlanClip, ...], videos: tuple[VideoAsset, ...], project: Project) -> None:
        """Cross-model validation: ownership and real source-time bounds."""
        by_id = {v.id: v for v in videos}
        for clip in clips:
            if clip.video_id not in project.video_ids or clip.video_id not in by_id:
                raise AppError(ErrorCode.INVALID_PLAN, "클립이 다른 프로젝트의 영상을 가리킵니다.")
            if clip.end_ms > by_id[clip.video_id].duration_ms:
                raise AppError(ErrorCode.INVALID_PLAN, "클립이 원본 영상 길이를 초과합니다.")

    def create(
        self, result: RecommendationResult, project: Project, videos: tuple[VideoAsset, ...],
        subtitle_style: SubtitleStyle = SubtitleStyle.BASIC,
    ) -> EditPlan:
        if result.project_id != project.id:
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 프로젝트 ID 불일치")
        clips = tuple(
            PlanClip(id=new_id(), video_id=clip.video_id, start_ms=clip.start_ms,
                     end_ms=clip.end_ms, source_recommendation_clip_id=clip.id)
            for clip in result.clips
        )
        self.validate_clips(clips, videos, project)
        return EditPlan(
            id=new_id(), project_id=project.id, recommendation_id=result.id,
            version=1, clips=clips, subtitle_style=subtitle_style,
        )

    def revise(
        self, current: EditPlan, expected_version: int, clips: tuple[PlanClip, ...],
        project: Project, videos: tuple[VideoAsset, ...],
    ) -> EditPlan:
        if current.status != PlanStatus.DRAFT or current.version != expected_version:
            raise AppError(ErrorCode.PLAN_CONFLICT, "수정 가능한 최신 초안이 아닙니다.")
        self.validate_clips(clips, videos, project)
        return EditPlan.model_validate({
            **current.model_dump(), "version": current.version + 1,
            "clips": clips, "approved_at": None,
        })

    def approve(
        self, current: EditPlan, expected_version: int, project: Project,
        videos: tuple[VideoAsset, ...],
    ) -> ApprovedEditPlan:
        if current.status != PlanStatus.DRAFT or current.version != expected_version:
            raise AppError(ErrorCode.PLAN_CONFLICT, "이미 승인되었거나 오래된 초안입니다.")
        if not current.clips:
            raise AppError(ErrorCode.INVALID_PLAN, "선택된 영상 구간이 없습니다.")
        self.validate_clips(current.clips, videos, project)
        return ApprovedEditPlan.model_validate({
            **current.model_dump(), "status": PlanStatus.APPROVED,
            "approved_at": utc_now(),
        })
