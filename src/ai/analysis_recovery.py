"""Disk-backed, validated partial analysis cache and bounded transient retries."""

import hashlib
import json
import logging
import os
from pathlib import Path
from random import uniform
from tempfile import NamedTemporaryFile
from time import sleep
from typing import Callable, TypeVar

from pydantic import BaseModel

from ai.config import AISettings
from ai.providers.gemini import GeminiProcessingError


logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


def transient_retry(operation: Callable[[], T], *, stage: str, retries: int,
                    settings: AISettings) -> T:
    """Retry transport/service failures only, never invalid output or references."""
    for attempt in range(retries + 1):
        try:
            return operation()
        except GeminiProcessingError as exc:
            code = getattr(exc.__cause__, "code", None)
            code = code if type(code) is int else None
            logger.warning("Gemini %s 실패 — 시도 %d/%d, HTTP %s, retryable=%s",
                           stage, attempt + 1, retries + 1, code, exc.retryable)
            if not exc.retryable or attempt >= retries:
                raise
            delay = min(settings.analysis_retry_max_delay_seconds,
                        settings.analysis_retry_base_delay_seconds * 2 ** attempt + uniform(0, 1))
            logger.info("Gemini %s 재시도 — %.2f초 후", stage, delay)
            sleep(delay)
    raise AssertionError("unreachable")


class PartialAnalysisCache:
    """Content-addressed cache, isolated by processed transcript and exact Map request.

    Only schema- and reference-validated data is persisted. Atomic replace means
    concurrent writers cannot expose a half-written cache file.
    """

    VERSION = "map-cache-v1"

    def __init__(self, settings: AISettings, transcript_json: str):
        self.root = settings.analysis_cache_dir if settings.analysis_cache_enabled else None
        self.transcript_key = hashlib.sha256(transcript_json.encode("utf-8")).hexdigest()
        self.model = settings.gemini_model
        self.thinking = settings.analysis_map_thinking_level

    def path(self, prompt: str, schema: type[T]) -> Path | None:
        if self.root is None:
            return None
        identity = json.dumps({
            "version": self.VERSION,
            "model": self.model,
            "thinking": self.thinking,
            "schema": schema.model_json_schema(),
            "prompt": prompt,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.root / self.transcript_key / (key + ".json")

    @staticmethod
    def load(path: Path | None, schema: type[T], validate: Callable[[T], object]) -> T | None:
        if path is None:
            return None
        try:
            result = schema.model_validate_json(path.read_text(encoding="utf-8"))
            validate(result)
            return result
        except FileNotFoundError:
            return None
        except (OSError, ValueError, GeminiProcessingError) as exc:
            logger.warning("부분 분석 캐시 읽기 실패 — %s", type(exc).__name__)
            return None

    @staticmethod
    def save(path: Path | None, result: BaseModel) -> None:
        if path is None:
            return
        temp = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                    suffix=".tmp", delete=False) as stream:
                temp = Path(stream.name)
                stream.write(result.model_dump_json())
            os.replace(temp, path)
            temp = None
        except OSError as exc:
            logger.warning("부분 분석 캐시 저장 실패 — %s", type(exc).__name__)
        finally:
            if temp is not None:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
