"""Create a team-safe starter ZIP without local Python environments or API secrets.

Run from the project root:
    python scripts/build_starter_zip.py

The output is written beside the project directory as VideoAssistant_Starter.zip.
"""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "VideoAssistant_Starter.zip"
ROOT_FILES = {".env.example", ".gitignore", "README.md", "pyproject.toml", "RECOMMENDATION_WALKTHROUGH.md"}
FOLDERS = {"src", "tests", "docs", "scripts", "examples"}
ALLOWED_SUFFIXES = {".py", ".md", ".toml", ".mp4", ".json", ".txt"}
IGNORED_PARTS = {".venv", "__pycache__", ".pytest_cache", ".git", "runtime", ".mypy_cache", ".ruff_cache"}


def include( path: Path ) -> bool:
    relative = path.relative_to(ROOT)
    if set(relative.parts) & IGNORED_PARTS or path.name.startswith(".env"):
        return path.name == ".env.example"
    if len(relative.parts) == 1:
        return path.name in ROOT_FILES
    if relative.parts[0] not in FOLDERS:
        return False
    if path.name.endswith((".pyc", ".pyo")) or ".egg-info" in path.as_posix():
        return False
    return path.suffix.lower() in ALLOWED_SUFFIXES


def main() -> None:
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and include(path))
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=(Path("VideoAssistant") / path.relative_to(ROOT)).as_posix())
    print(f"Created: {OUTPUT} ({len(files)} files)")


if __name__ == "__main__":
    main()
