import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core.models import (
    ApprovedEditPlan, PlanClip, ShortsTemplate, SubtitleStyle, Transcript, TranscriptSegment,
    VideoAsset, utc_now,
)
from processing.ffmpeg import LANDSCAPE, SHORTS, FFmpegVideoEditor, build_ass, title_filters
from processing.files import probe_video

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo.mp4"


def make_plan(template=None, title_lines=(), clips=((0, 1000),)) -> ApprovedEditPlan:
    return ApprovedEditPlan(
        id="plan1", project_id="p1", recommendation_id="r1", version=1,
        clips=tuple(
            PlanClip(id=f"c{i}", video_id="v1", start_ms=s, end_ms=e)
            for i, (s, e) in enumerate(clips)
        ),
        shorts_template=template, title_lines=title_lines, approved_at=utc_now(),
    )


def test_plan_without_template_is_landscape():
    plan = make_plan()
    assert plan.shorts_template is None
    assert plan.title_lines == ()


@pytest.mark.parametrize("title_lines", [
    ("1", "2", "3"),
    ("가" * 21,),
    ("   ",),
])
def test_plan_rejects_invalid_title_lines(title_lines):
    with pytest.raises(ValueError):
        make_plan(ShortsTemplate.BLACK, title_lines)


def test_build_ass_scales_for_shorts():
    ass = build_ass([(0, 1000, "안녕")], SubtitleStyle.BASIC, "Malgun Gothic", SHORTS)
    assert "PlayResX: 720" in ass and "PlayResY: 1280" in ass
    style = next(line for line in ass.splitlines() if line.startswith("Style:"))
    assert style.startswith("Style: Default,Malgun Gothic,44,")
    assert style.endswith(f",0,2,20,20,{SHORTS.margin_v}")


def test_build_ass_landscape_unchanged():
    ass = build_ass([(0, 1000, "안녕")], SubtitleStyle.BASIC, "Malgun Gothic", LANDSCAPE)
    assert "PlayResX: 640" in ass
    assert ",Malgun Gothic,20," in ass


def test_title_filters_use_template_colors():
    black = title_filters(ShortsTemplate.BLACK, ("보고도", "못 믿을"))
    white = title_filters(ShortsTemplate.WHITE, ("보고도",))
    assert len(black) == 2 and "fontcolor=0xFFFFFF" in black[0] and "fontcolor=0xFFE500" in black[1]
    assert len(white) == 1 and "fontcolor=0x000000" in white[0]
    assert all("textfile=" in f and "expansion=none" in f for f in black)


def _has_filters(*names: str) -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return all(f" {name} " in out for name in names)


needs_ffmpeg = pytest.mark.skipif(
    not DEMO.exists() or not _has_filters("ass", "drawtext"), reason="ffmpeg(libass, drawtext) / demo.mp4 없음",
)


def _demo_video() -> VideoAsset:
    duration_ms, has_audio = probe_video(DEMO)
    return VideoAsset(
        id="v1", project_id="p1", filename="demo.mp4", source_path=DEMO,
        duration_ms=duration_ms, sha256=hashlib.sha256(DEMO.read_bytes()).hexdigest(),
        has_audio=has_audio,
    )


def _size(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "json", str(path)], capture_output=True, text=True, check=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return stream["width"], stream["height"]


@needs_ffmpeg
@pytest.mark.parametrize("template, title_lines", [
    (ShortsTemplate.BLACK, ("보고도", "못 믿을 AI 편집")),
    (ShortsTemplate.WHITE, ("특수문자: 100% 'OK'",)),
    (ShortsTemplate.BLACK, ()),
])
def test_render_shorts(tmp_path, template, title_lines):
    transcript = Transcript(
        id="t1", video_id="v1", transcriber_version="test",
        segments=(TranscriptSegment(id="s0", start_ms=0, end_ms=1500, text="자막"),),
    )
    output = tmp_path / "out.mp4"

    result = FFmpegVideoEditor().render(
        (_demo_video(),), (transcript,), make_plan(template, title_lines, ((0, 1000), (1200, 2000))), output,
    )

    assert _size(output) == (720, 1280)
    assert abs(result.duration_ms - 1800) < 200


@needs_ffmpeg
def test_render_without_template_stays_landscape(tmp_path):
    output = tmp_path / "out.mp4"
    FFmpegVideoEditor().render((_demo_video(),), (None,), make_plan(), output)
    assert _size(output) == (640, 360)