"""AI 모듈 전용 실행 설정.

API 키와 제공자 선택은 환경변수 또는 프로젝트 루트의 .env에서 읽습니다.
프로젝트의 다른 패키지나 bootstrap.py를 수정하지 않습니다.
"""

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AIProvider(StrEnum):
    """AI 구현 제공자. OpenAI와 Ollama는 추후 구현을 위한 예약 값입니다."""

    RULE_BASED = "rule_based"
    GEMINI = "gemini"
    OPENAI = "openai"
    OLLAMA = "ollama"


class AIFallbackPolicy(StrEnum):
    """Gemini 요청 또는 응답 검증 실패 시 적용할 정책."""

    RAISE = "raise"
    RULE_BASED = "rule_based"


@dataclass(frozen=True)
class AISettings:
    """AI-01 설정. 기본 제공자는 Gemini, 실패 시 규칙 기반으로 전환합니다."""

    provider: AIProvider = AIProvider.GEMINI
    fallback: AIFallbackPolicy = AIFallbackPolicy.RULE_BASED
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    preprocessing_concurrency: int = 3

    def __post_init__(self) -> None:
        if not isinstance(self.provider, AIProvider):
            raise ValueError("provider는 AIProvider 열거형이어야 합니다.")
        if not isinstance(self.fallback, AIFallbackPolicy):
            raise ValueError("fallback은 AIFallbackPolicy 열거형이어야 합니다.")
        if type(self.preprocessing_concurrency) is not int or not 1 <= self.preprocessing_concurrency <= 8:
            raise ValueError("PREPROCESSING_CONCURRENCY는 1~8 정수여야 합니다.")
        if not self.gemini_model.strip():
            raise ValueError("gemini_model은 비어 있을 수 없습니다.")

    @classmethod
    def from_env(cls) -> "AISettings":
        """운영체제 환경변수 > 프로젝트 .env > 코드 기본값 순서로 읽습니다."""
        file_values = dotenv_values(PROJECT_ROOT / ".env")

        def read(name: str) -> str | None:
            value = os.environ.get(name)
            if value is None:
                value = file_values.get(name)
            return value.strip() if isinstance(value, str) else None

        provider_value = read("AI_PROVIDER") or AIProvider.GEMINI.value
        fallback_value = read("AI_FALLBACK") or AIFallbackPolicy.RULE_BASED.value
        try:
            provider = AIProvider(provider_value.lower())
            fallback = AIFallbackPolicy(fallback_value.lower())
        except ValueError as exc:
            raise ValueError("AI_PROVIDER 또는 AI_FALLBACK 설정값이 올바르지 않습니다.") from exc

        return cls(
            provider=provider,
            fallback=fallback,
            gemini_api_key=read("GEMINI_API_KEY") or read("GOOGLE_API_KEY"),
            gemini_model=read("GEMINI_MODEL") or cls.gemini_model,
            preprocessing_concurrency=int(read("PREPROCESSING_CONCURRENCY") or cls.preprocessing_concurrency),
        )
