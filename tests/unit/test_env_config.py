"""Verify .env loading, default values and precedence without changing project files."""

import os
from pathlib import Path
from unittest.mock import patch

from video_assistant.core.config import Settings


def test_env_file_sets_backend_and_exposes_api_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'RECOMMENDER_BACKEND=keyword\nANALYZER_BACKEND=simple\nOPENAI_API_KEY=test-only-key\n',
        encoding="utf-8",
    )

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings.from_env(env_file)
        assert settings.recommender_backend == "keyword"
        assert settings.analyzer_backend == "simple"
        assert settings.transcriber_backend == "stub"
        assert settings.editor_backend == "stub"
        assert os.environ["OPENAI_API_KEY"] == "test-only-key"


def test_os_environment_overrides_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("RECOMMENDER_BACKEND=stub\nMAX_UPLOAD_MB=20\n", encoding="utf-8")

    with patch.dict(os.environ, {"RECOMMENDER_BACKEND": "keyword", "MAX_UPLOAD_MB": "75"}, clear=True):
        settings = Settings.from_env(env_file)
        assert settings.recommender_backend == "keyword"
        assert settings.max_upload_mb == 75


def test_missing_dotenv_uses_defaults(tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings.from_env(tmp_path / "does_not_exist.env")
        assert settings.recommender_backend == "stub"
        assert settings.analyzer_backend == "stub"
        assert settings.max_upload_mb == 200


def test_explicit_settings_do_not_load_dotenv(tmp_path):
    (tmp_path / ".env").write_text("RECOMMENDER_BACKEND=keyword\n", encoding="utf-8")
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(runtime_dir=tmp_path, recommender_backend="stub")
        assert settings.recommender_backend == "stub"
        assert "RECOMMENDER_BACKEND" not in os.environ


def test_project_root_dotenv_used_independent_of_working_directory(tmp_path, monkeypatch):
    from video_assistant.core import config

    (tmp_path / ".env").write_text("RECOMMENDER_BACKEND=keyword\n", encoding="utf-8")
    monkeypatch.setattr(config, "_PROJECT_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path.parent)

    with patch.dict(os.environ, {}, clear=True):
        assert Settings.from_env().recommender_backend == "keyword"
