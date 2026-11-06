"""One-process configuration. Read project .env without overwriting shell variables."""

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field


# src/application/config.py -> parents[2] points at the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    """Select implementations and runtime file location without changing source."""

    runtime_dir: Path = Path("runtime")
    transcriber_backend: str = "stub"
    preprocessor_backend: str = "stub"
    analyzer_backend: str = "stub"
    project_analyzer_backend: str = "stub"
    recommender_backend: str = "stub"
    editor_backend: str = "stub"

    @classmethod
    def from_env(cls) -> "Settings":
        """Priority: active OS environment > project .env > defaults."""
        values = dotenv_values(PROJECT_ROOT / ".env")
        names = cls.model_fields
        selected = {}
        for key in names:
            env_name = key.upper()
            value = os.environ.get(env_name, values.get(env_name))
            if value is not None and value != "":
                selected[key] = value
        settings = cls(**selected)
        if not settings.runtime_dir.is_absolute():
            settings.runtime_dir = (PROJECT_ROOT / settings.runtime_dir).resolve()
        return settings
