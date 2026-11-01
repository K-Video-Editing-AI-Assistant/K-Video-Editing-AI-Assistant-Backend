"""Shared data contracts for the AI video-editing assistant (Pydantic v2)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class PlanStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class JobKind(StrEnum):
    PREPARE = "prepare"
    RECOMMEND = "recommend"
    RENDER = "render"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobStage(StrEnum):
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    RECOMMENDING = "recommending"
    RENDERING = "rendering"
    VALIDATING = "validating"


class VideoAsset(ContractModel):
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    source_path: Path
    original_name: str = Field(min_length=1)
    duration_ms: int = Field(strict=True, gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    has_audio: bool
    created_at: AwareDatetime = Field(default_factory=utc_now)


class TranscriptSegment(ContractModel):
    id: str = Field(min_length=1)
    start_ms: int = Field(strict=True, ge=0)
    end_ms: int = Field(strict=True, gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.start_ms >= self.end_ms:
            raise ValueError("A segment must satisfy start_ms < end_ms")
        return self


class Transcript(ContractModel):
    id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    segments: tuple[TranscriptSegment, ...]
    transcriber_version: str = Field(min_length=1)
    is_stub: bool = False
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_segments(self) -> Self:
        ids = [segment.id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("Transcript segment IDs must be unique")
        previous_end = 0
        for segment in self.segments:
            if segment.start_ms < previous_end:
                raise ValueError("Transcript segments must be ordered and non-overlapping")
            previous_end = segment.end_ms
        return self


class TopicSection(ContractModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    start_ms: int = Field(strict=True, ge=0)
    end_ms: int = Field(strict=True, gt=0)
    segment_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_topic(self) -> Self:
        if self.start_ms >= self.end_ms:
            raise ValueError("A topic must satisfy start_ms < end_ms")
        if any(not segment_id.strip() for segment_id in self.segment_ids):
            raise ValueError("Topic segment IDs must not be blank")
        if len(set(self.segment_ids)) != len(self.segment_ids):
            raise ValueError("Topic segment IDs must be unique")
        return self


class VideoAnalysis(ContractModel):
    id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    transcript_id: str = Field(min_length=1)
    summary: str
    topics: tuple[TopicSection, ...]
    analyzer_version: str = Field(min_length=1)
    is_stub: bool = False
    created_at: AwareDatetime = Field(default_factory=utc_now)


class SearchRequest(ContractModel):
    id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    max_clips: int = Field(default=5, strict=True, ge=1, le=20)
    created_at: AwareDatetime = Field(default_factory=utc_now)


class ClipSelection(ContractModel):
    id: str = Field(min_length=1)
    start_ms: int = Field(strict=True, ge=0)
    end_ms: int = Field(strict=True, gt=0)
    reason: str = ""
    source_segment_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_clip(self) -> Self:
        if self.start_ms >= self.end_ms:
            raise ValueError("A clip must satisfy start_ms < end_ms")
        if any(not segment_id.strip() for segment_id in self.source_segment_ids):
            raise ValueError("Source segment IDs must not be blank")
        if len(self.source_segment_ids) != len(set(self.source_segment_ids)):
            raise ValueError("Source segment IDs must be unique")
        return self


class RecommendationResult(ContractModel):
    id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    transcript_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    clips: tuple[ClipSelection, ...]
    recommender_version: str = Field(min_length=1)
    is_stub: bool = False
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_clip_ids(self) -> Self:
        ids = [clip.id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("Recommended clip IDs must be unique")
        return self


class EditPlan(ContractModel):
    id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    recommendation_id: str = Field(min_length=1)
    version: int = Field(strict=True, ge=1)
    clips: tuple[ClipSelection, ...]
    status: PlanStatus = PlanStatus.DRAFT
    created_at: AwareDatetime = Field(default_factory=utc_now)
    approved_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        ids = [clip.id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan clip IDs must be unique")
        if self.status == PlanStatus.APPROVED:
            if self.approved_at is None or not self.clips:
                raise ValueError("An approved plan requires approved_at and at least one clip")
        elif self.approved_at is not None:
            raise ValueError("Draft plans cannot have approved_at")
        return self


class ApprovedEditPlan(EditPlan):
    status: Literal[PlanStatus.APPROVED] = PlanStatus.APPROVED


class RenderResult(ContractModel):
    id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    plan_version: int = Field(strict=True, ge=1)
    output_path: Path
    duration_ms: int = Field(strict=True, gt=0)
    renderer_version: str = Field(min_length=1)
    is_stub: bool = False
    created_at: AwareDatetime = Field(default_factory=utc_now)


class JobStatus(ContractModel):
    id: str = Field(min_length=1)
    kind: JobKind
    project_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    state: JobState = JobState.QUEUED
    stage: JobStage | None = None
    progress: int | None = Field(default=None, strict=True, ge=0, le=100)
    result_ref: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    submitted_at: AwareDatetime = Field(default_factory=utc_now)
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.state == JobState.FAILED:
            if not self.error_code or not self.error_message or self.finished_at is None:
                raise ValueError("Failed jobs require an error and finished_at")
        elif self.error_code is not None or self.error_message is not None:
            raise ValueError("Only failed jobs may contain error details")
        if self.state == JobState.SUCCEEDED:
            if not self.result_ref or self.finished_at is None or self.progress != 100:
                raise ValueError("Successful jobs require result_ref, finished_at and progress=100")
        if self.state in (JobState.QUEUED, JobState.RUNNING) and self.finished_at is not None:
            raise ValueError("Unfinished jobs cannot have finished_at")
        return self
