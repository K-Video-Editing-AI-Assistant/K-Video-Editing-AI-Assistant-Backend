"""Runtime configuration from the project's .env file and OS environment.

Priority: OS environment > project-root .env > built-in defaults.
Use Settings(...) explicitly in tests to bypass automatic configuration loading.
"""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

from .errors import AppError, ErrorCode


_PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    runtime_dir: Path
    max_upload_mb: int = 200
    transcriber_backend: str = "stub"
    analyzer_backend: str = "stub"
    recommender_backend: str = "stub"
    editor_backend: str = "stub"

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        """Load project-root .env without replacing existing OS environment values.

        env_file is optional and mainly useful for isolated tests or tooling.
        Values loaded by python-dotenv are also available to real adapters via
        os.getenv(), e.g. LLM API keys. Restart the app after editing .env.
        """
        dotenv_path = env_file if env_file is not None else _PROJECT_ROOT / ".env"
        load_dotenv(dotenv_path=dotenv_path, override=False)

        return cls(
            runtime_dir=Path(os.getenv("VIDEO_ASSISTANT_RUNTIME_DIR", "runtime")).resolve(),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "200")),
            transcriber_backend=os.getenv("TRANSCRIBER_BACKEND", "stub"),
            analyzer_backend=os.getenv("ANALYZER_BACKEND", "stub"),
            recommender_backend=os.getenv("RECOMMENDER_BACKEND", "stub"),
            editor_backend=os.getenv("EDITOR_BACKEND", "stub"),
        )

    def validate(self) -> None:
        if self.max_upload_mb <= 0:
            raise AppError(ErrorCode.INVALID_INPUT, "MAX_UPLOAD_MB는 양수여야 합니다.")
        for name in ("transcriber_backend", "analyzer_backend", "recommender_backend", "editor_backend"):
            if not getattr(self, name).strip():
                raise AppError(ErrorCode.INVALID_INPUT, f"{name} 값이 비어 있습니다.")
