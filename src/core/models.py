"""CLIPNOTE의 공통 데이터 모델(Pydantic v2).

팀 전체가 전달하는 데이터의 **형식**을 이 파일에서 정의합니다.
- 모든 시간은 정수 밀리초(ms)입니다. 구간은 [start_ms, end_ms)로 해석합니다.
- 한 Project는 여러 VideoAsset을 가질 수 있습니다.
- AI 추천(RecommendationClip)과 사용자 편집 지시(PlanClip)는 분리합니다.
- 개별 필드/한 객체 내부는 이 파일에서 검증합니다.
- 실제 프로젝트/영상/자막 간의 참조 관계는 application 계층에서 검증합니다.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def new_id() -> str:
    """새 리소스 식별자를 생성합니다. 팀원은 동일한 형식의 문자열 ID를 사용합니다."""
    return uuid4().hex


def utc_now() -> datetime:
    """시간대 정보가 포함된 현재 UTC 시각을 반환합니다."""
    return datetime.now(timezone.utc)


class ContractModel(BaseModel):
    """모든 계약 모델의 부모. 잘못된 추가 필드와 생성 후의 값 변경을 방지합니다."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TimeRange(ContractModel):
    """영상 구간의 공통 시간 규칙. 시작은 포함, 끝은 포함하지 않습니다."""

    start_ms: int = Field(ge=0, strict=True, description="원본 영상 기준 시작 시각(ms)")
    end_ms: int = Field(gt=0, strict=True, description="원본 영상 기준 종료 시각(ms)")

    @model_validator(mode="after")
    def check_range(self) -> "TimeRange":
        """길이가 0 또는 음수인 구간을 거부합니다."""
        if self.start_ms >= self.end_ms:
            raise ValueError("start_ms must be less than end_ms")
        return self


# -----------------------------------------------------------------------------
# 1. 사용자가 등록한 프로젝트와 원본 영상: Application / 영상처리 담당
# -----------------------------------------------------------------------------

class EditMode(str, Enum):
    """AI 추천 순서 정책. 렌더러는 결정된 clips 배열 순서만 따릅니다."""

    PRESERVE_ORDER = "preserve_order"       # 원본 영상 및 원본 시간 순서 유지
    GROUP_BY_TOPIC = "group_by_topic"       # 같은 주제별로 모아서 추천


class SubtitleStyle(str, Enum):
    """최종 영상에 적용할 자막 표시 스타일."""

    BASIC = "basic"                         # 일반 자막
    BOLD = "bold"                           # 강조 자막
    BOX = "box"                             # 배경 박스가 있는 자막


class Project(ContractModel):
    """하나의 편집 작업. 여러 원본 영상 ID를 같은 프로젝트로 묶습니다."""

    id: str = Field(min_length=1, description="프로젝트 식별자")
    title: str = Field(min_length=1, description="프로젝트 제목")
    video_ids: tuple[str, ...] = Field(default=(), description="프로젝트 소속 원본 영상 ID 목록")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def check_video_ids(self) -> "Project":
        """같은 영상 ID를 프로젝트에 중복 등록하지 않습니다."""
        if len(self.video_ids) != len(set(self.video_ids)):
            raise ValueError("duplicate project video IDs")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class VideoAsset(ContractModel):
    """저장된 원본 영상 하나. 파일 경로는 로컬 실행 환경 기준입니다."""

    id: str = Field(min_length=1, description="영상 식별자")
    project_id: str = Field(min_length=1, description="소속 프로젝트 ID")
    filename: str = Field(min_length=1, description="사용자가 업로드한 파일명")
    source_path: Path = Field(description="실제 원본 파일 경로")
    duration_ms: int = Field(gt=0, strict=True, description="FFprobe로 확인한 영상 길이(ms)")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$", description="파일 내용 해시(캐시 판별용)")
    has_audio: bool = Field(description="오디오 스트림 존재 여부")
    created_at: datetime = Field(default_factory=utc_now)


# -----------------------------------------------------------------------------
# 2. 자막: 영상처리 결과(원본)와 AI 전처리 결과를 구분
# -----------------------------------------------------------------------------

class TranscriptSegment(TimeRange):
    """Whisper가 생성한 하나의 발언 구간."""

    id: str = Field(min_length=1, description="원본 발언 식별자")
    text: str = Field(min_length=1, description="인식한 발언 내용")


class Transcript(ContractModel):
    """원본 영상 하나에 대한 음성 인식 결과. 무음이면 segments=()도 정상입니다."""

    id: str = Field(min_length=1, description="자막 결과 식별자")
    video_id: str = Field(min_length=1, description="원본 영상 ID")
    segments: tuple[TranscriptSegment, ...] = Field(default=(), description="시작 시간순 자막")
    language: str = Field(default="ko", min_length=1, description="인식 언어 코드")
    transcriber_version: str = Field(min_length=1, description="음성 인식 구현 및 모델 버전")
    is_stub: bool = Field(default=False, description="테스트용 더미 데이터 여부")

    @model_validator(mode="after")
    def check_segments(self) -> "Transcript":
        """ID 중복과 정렬 오류를 방지합니다. 화자별 발언 겹침은 허용합니다."""
        ids = [segment.id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate transcript segment IDs")
        if list(self.segments) != sorted(self.segments, key=lambda segment: segment.start_ms):
            raise ValueError("transcript segments must be sorted by start_ms")
        return self


class ProcessedSegment(TimeRange):
    """AI가 정리한 자막 구간. 원본 발언 ID를 반드시 기억합니다."""

    id: str = Field(min_length=1, description="전처리 구간 ID")
    text: str = Field(min_length=1, description="전처리된 텍스트")
    source_segment_ids: tuple[str, ...] = Field(min_length=1, description="해당하는 원본 발언 ID")


class ProcessedTranscript(ContractModel):
    """원본 자막에서 파생된 AI 입력 자료. 원본 Transcript 자체는 변경하지 않습니다."""

    id: str = Field(min_length=1, description="전처리 결과 ID")
    video_id: str = Field(min_length=1, description="원본 영상 ID")
    source_transcript_id: str = Field(min_length=1, description="전처리 이전 원본 Transcript ID")
    segments: tuple[ProcessedSegment, ...] = ()
    preprocessing_version: str = Field(min_length=1, description="전처리 규칙 버전")
    is_stub: bool = False

    @model_validator(mode="after")
    def check_segments(self) -> "ProcessedTranscript":
        """전처리 구간 ID는 중복되지 않아야 합니다."""
        ids = [segment.id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate processed segment IDs")
        if list(self.segments) != sorted(self.segments, key=lambda segment: segment.start_ms):
            raise ValueError("processed segments must be sorted by start_ms")
        return self


# -----------------------------------------------------------------------------
# 3. AI 분석: 영상 단위 분석과 프로젝트 단위 집계를 분리
# -----------------------------------------------------------------------------

class TopicSection(TimeRange):
    """영상 속 한 주제. 원본 발언 ID로 설명 근거를 표시합니다."""

    id: str = Field(min_length=1, description="주제 ID")
    title: str = Field(min_length=1, description="주제의 짧은 이름")
    description: str = Field(default="", description="주제 설명")
    source_segment_ids: tuple[str, ...] = Field(min_length=1, description="이 주제의 원본 자막 ID")


class VideoAnalysis(ContractModel):
    """영상 하나의 요약과 주제 분석. 사용자 요청과 관계없이 재사용합니다."""

    id: str = Field(min_length=1, description="영상 분석 결과 ID")
    video_id: str = Field(min_length=1, description="분석 대상 영상 ID")
    transcript_id: str = Field(min_length=1, description="분석 근거가 된 원본 자막 ID")
    processed_transcript_id: str = Field(min_length=1, description="실제로 분석한 전처리 자막 ID")
    summary: str = Field(default="", description="영상 전체 요약. 무음 영상에서는 빈 문자열 가능")
    topics: tuple[TopicSection, ...] = ()
    analyzer_version: str = Field(min_length=1, description="분석 모델·프롬프트 버전")
    is_stub: bool = False

    @model_validator(mode="after")
    def check_topics(self) -> "VideoAnalysis":
        """같은 분석 결과 안에서 주제 ID는 고유해야 합니다."""
        ids = [topic.id for topic in self.topics]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate topic IDs")
        return self


class KeywordSuggestion(ContractModel):
    """프로젝트에서 추천할 검색 키워드 하나."""

    keyword: str = Field(min_length=1, description="화면에 보여 줄 키워드")
    reason: str = Field(default="", description="추천 이유")
    topic_ids: tuple[str, ...] = Field(default=(), description="키워드 근거가 되는 주제 ID")


class ProjectAnalysis(ContractModel):
    """여러 영상 분석 결과를 모아 하나의 프로젝트로 보여주기 위한 요약 자료."""

    id: str = Field(min_length=1, description="프로젝트 분석 결과 ID")
    project_id: str = Field(min_length=1, description="소속 프로젝트 ID")
    video_analysis_ids: tuple[str, ...] = Field(min_length=1, description="영상별 분석 결과 ID")
    suggested_keywords: tuple[KeywordSuggestion, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def check_analysis_ids(self) -> "ProjectAnalysis":
        """같은 영상 분석 결과를 두 번 집계하지 않습니다."""
        if len(self.video_analysis_ids) != len(set(self.video_analysis_ids)):
            raise ValueError("duplicate video analysis IDs")
        return self


# -----------------------------------------------------------------------------
# 4. 검색·추천: 사용자의 자연어 요청에 따라 매번 새로 만드는 결과
# -----------------------------------------------------------------------------

class SearchRequest(ContractModel):
    """사용자가 원하는 장면과 검색 대상 영상을 나타냅니다."""

    id: str = Field(min_length=1, description="요청 ID")
    project_id: str = Field(min_length=1, description="소속 프로젝트 ID")
    video_ids: tuple[str, ...] = Field(min_length=1, description="요청에서 검색할 원본 영상 ID")
    query: str = Field(min_length=1, description="사용자 자연어 요청")
    max_clips: int = Field(default=5, ge=1, le=20, strict=True, description="최대 추천 구간 수")
    edit_mode: EditMode = EditMode.PRESERVE_ORDER
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def check_request(self) -> "SearchRequest":
        """빈 검색어·중복 대상 영상은 허용하지 않습니다."""
        if not self.query.strip():
            raise ValueError("query must not be blank")
        if len(self.video_ids) != len(set(self.video_ids)):
            raise ValueError("duplicate target video IDs")
        return self


class RecommendationClip(TimeRange):
    """AI가 제안한 원본 영상의 클립. 사용자가 편집해도 이 데이터는 보존합니다."""

    id: str = Field(min_length=1, description="추천 클립 ID")
    video_id: str = Field(min_length=1, description="어느 원본 영상의 구간인지 식별")
    reason: str = Field(default="", description="사용자에게 보여 줄 추천 이유")
    source_segment_ids: tuple[str, ...] = Field(min_length=1, description="추천 근거 원본 발언 ID")


class RecommendedTopic(ContractModel):
    """추천 클립을 주제별로 묶어 UI 카드에 표시할 때 사용합니다."""

    id: str = Field(min_length=1, description="추천 주제 그룹 ID")
    title: str = Field(min_length=1, description="그룹 제목")
    description: str = ""
    clip_ids: tuple[str, ...] = Field(min_length=1, description="이 그룹에 속하는 추천 클립 ID")


class RecommendationResult(ContractModel):
    """AI 추천 결과. 빈 추천은 clips=(), topics=()인 정상 응답입니다."""

    id: str = Field(min_length=1, description="추천 결과 ID")
    project_id: str = Field(min_length=1, description="소속 프로젝트 ID")
    request_id: str = Field(min_length=1, description="원본 SearchRequest ID")
    project_analysis_id: str = Field(min_length=1, description="참조한 프로젝트 분석 결과 ID")
    suggested_title: str = Field(default="", description="추천 결과용 제목")
    clips: tuple[RecommendationClip, ...] = ()   # 배열 순서가 AI의 제안 편집 순서
    topics: tuple[RecommendedTopic, ...] = ()
    recommender_version: str = Field(min_length=1, description="검색·추천 구현 버전")
    is_stub: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def check_references(self) -> "RecommendationResult":
        """추천 안의 클립 ID 중복과 존재하지 않는 주제 참조를 막습니다."""
        clip_ids = [clip.id for clip in self.clips]
        topic_ids = [topic.id for topic in self.topics]
        if len(clip_ids) != len(set(clip_ids)) or len(topic_ids) != len(set(topic_ids)):
            raise ValueError("duplicate recommendation clip or topic IDs")
        known_clips = set(clip_ids)
        for topic in self.topics:
            if not set(topic.clip_ids).issubset(known_clips):
                raise ValueError("recommended topic references an unknown clip")
        return self


# -----------------------------------------------------------------------------
# 5. 편집 계획: 채택·시간·순서를 수정하고 승인하면 고정
# -----------------------------------------------------------------------------

class PlanStatus(str, Enum):
    """편집 계획의 업무 상태. 렌더링은 APPROVED 상태만 허용합니다."""

    DRAFT = "draft"
    APPROVED = "approved"


class PlanClip(TimeRange):
    """실제로 편집할 클립. 추천과 달리 사용자가 시간을 수정할 수 있습니다."""

    id: str = Field(min_length=1, description="편집 계획 내부 클립 ID")
    video_id: str = Field(min_length=1, description="원본 영상 ID")
    source_recommendation_clip_id: str | None = Field(
        default=None, description="AI 추천에서 가져왔다면 원본 추천 클립 ID"
    )


class EditPlan(ContractModel):
    """사용자가 조정할 수 있는 계획. 수정 시 서비스가 새 버전을 저장합니다."""

    id: str = Field(min_length=1, description="편집 계획 ID")
    project_id: str = Field(min_length=1, description="프로젝트 ID")
    recommendation_id: str = Field(min_length=1, description="편집 초안을 만든 추천 결과 ID")
    version: int = Field(ge=1, strict=True, description="수정 때마다 증가하는 계획 버전")
    status: PlanStatus = PlanStatus.DRAFT
    clips: tuple[PlanClip, ...] = ()           # 목록 순서가 FFmpeg 렌더링 순서
    subtitle_style: SubtitleStyle = SubtitleStyle.BASIC
    edit_mode: EditMode = EditMode.PRESERVE_ORDER
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def check_plan(self) -> "EditPlan":
        """승인 시간과 상태가 일치해야 하고, 승인 계획에는 클립이 있어야 합니다."""
        ids = [clip.id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate plan clip IDs")
        if self.status == PlanStatus.APPROVED:
            if self.approved_at is None:
                raise ValueError("approved plan requires approved_at")
            if not self.clips:
                raise ValueError("cannot approve an empty plan")
        elif self.approved_at is not None:
            raise ValueError("draft plan cannot have approved_at")
        return self


class ApprovedEditPlan(EditPlan):
    """승인을 마친 스냅샷. 영상편집 담당자는 이 타입만 입력받습니다."""

    status: Literal[PlanStatus.APPROVED] = PlanStatus.APPROVED
    approved_at: datetime                  # DRAFT와 달리 승인 시각이 필수


# -----------------------------------------------------------------------------
# 6. 최종 영상과 장시간 작업 상태: 영상처리 / Application 담당
# -----------------------------------------------------------------------------

class RenderResult(ContractModel):
    """FFmpeg가 생성한 최종 출력 파일의 위치와 편집 이력."""

    id: str = Field(min_length=1, description="렌더링 결과 ID")
    project_id: str = Field(min_length=1, description="프로젝트 ID")
    plan_id: str = Field(min_length=1, description="사용한 승인 계획 ID")
    plan_version: int = Field(ge=1, strict=True, description="사용한 승인 계획 버전")
    output_path: Path = Field(description="출력 MP4 경로")
    duration_ms: int = Field(gt=0, strict=True, description="실제 영상 길이(ms)")
    used_clip_ids: tuple[str, ...] = Field(min_length=1, description="실제 사용한 PlanClip ID 목록")
    renderer_version: str = Field(min_length=1, description="편집기 구현 버전")
    is_stub: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class JobKind(str, Enum):
    """장시간 실행할 작업의 종류."""

    PREPARE = "prepare"                     # 음성 인식·영상 분석
    RECOMMEND = "recommend"                 # 자연어 구간 추천
    RENDER = "render"                       # 최종 영상 렌더링


class JobState(str, Enum):
    """작업 실행 상태(사용자 승인 대기는 EditPlan.status가 담당)."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobStatus(ContractModel):
    """Application 담당의 작업 관리자가 기록하고 UI가 조회하는 실행 상태."""

    id: str = Field(min_length=1, description="작업 ID")
    project_id: str = Field(min_length=1, description="소속 프로젝트 ID")
    video_id: str | None = Field(default=None, description="영상별 작업일 때 해당 영상 ID")
    kind: JobKind
    state: JobState = JobState.QUEUED
    progress: int = Field(default=0, ge=0, le=100, strict=True, description="진행률(0~100)")
    result_ref: str | None = Field(default=None, description="성공한 결과 객체의 ID")
    error_message: str | None = Field(default=None, description="실패 사유(사용자 표시용)")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def check_status(self) -> "JobStatus":
        """완료·실패 상태에는 결과/오류 정보가 각각 있어야 합니다."""
        if self.state == JobState.SUCCEEDED and not self.result_ref:
            raise ValueError("successful job requires result_ref")
        if self.state == JobState.FAILED and not self.error_message:
            raise ValueError("failed job requires error_message")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self
