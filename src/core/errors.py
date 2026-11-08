"""AI 영상편집 어시스턴트 기능 모듈이 공통으로 사용하는 애플리케이션 오류 계약.

Pydantic 필드 오류는 ValidationError, 업무 규칙·외부 처리 오류는 AppError로 구분합니다.
예: 잘못된 편집 계획은 INVALID_PLAN, 실제 FFmpeg 실패는 RENDER_FAILED입니다.
"""

from enum import Enum


class ErrorCode(str, Enum):
    """UI/작업자가 처리 유형을 판단하는 안정적인 오류 코드."""

    INVALID_INPUT = "invalid_input"           # 필수 입력·요청 값 오류
    NOT_FOUND = "not_found"                   # 대상 프로젝트/영상/결과 없음
    INVALID_REFERENCE = "invalid_reference"   # 다른 객체를 가리키는 ID가 잘못됨
    INVALID_PLAN = "invalid_plan"             # 편집 구간·승인 조건 위반
    PLAN_CONFLICT = "plan_conflict"           # 오래된 계획 버전으로 수정 시도
    TRANSCRIPTION_FAILED = "transcription_failed"
    ANALYSIS_FAILED = "analysis_failed"
    RECOMMENDATION_FAILED = "recommendation_failed"
    RENDER_FAILED = "render_failed"
    STORAGE_FAILED = "storage_failed"         # 파일/메타데이터 저장 실패
    OUTPUT_INVALID = "output_invalid"         # 렌더링 파일 검증 실패


class AppError(Exception):
    """공통 오류 코드, 설명, 재시도 가능 여부를 포함하는 예외."""

    def __init__(self, code: ErrorCode, message: str, retryable: bool = False) -> None:
        # 메시지는 UI에 표시하거나 JobStatus.error_message에 기록할 수 있습니다.
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
