import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from core.models import (
    ApprovedEditPlan, PlanClip, PlanSubtitle, SubtitleStyle, Transcript, TranscriptSegment,
    VideoAsset, utc_now,
)
from processing import ffmpeg
from processing.ffmpeg import (
    FFmpegVideoEditor, _ass_text, _ass_time, build_ass, edited_subtitle_events, subtitle_events,
)
from processing.files import probe_video

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo.mp4"


def make_transcript(*segments: tuple[int, int, str], video_id: str = "v1") -> Transcript:
    return Transcript(
        id="t1", video_id=video_id, transcriber_version="test",
        segments=tuple(
            TranscriptSegment(id=f"s{i}", start_ms=s, end_ms=e, text=text)
            for i, (s, e, text) in enumerate(segments)
        ),
    )


def make_plan(*clips: tuple[int, int], style=SubtitleStyle.BASIC, subtitles=None) -> ApprovedEditPlan:
    return ApprovedEditPlan(
        id="plan1", project_id="p1", recommendation_id="r1", version=1,
        clips=tuple(
            PlanClip(id=f"c{i}", video_id="v1", start_ms=s, end_ms=e)
            for i, (s, e) in enumerate(clips)
        ),
        subtitle_style=style, subtitles=subtitles, approved_at=utc_now(),
    )


def test_subtitle_events_are_shifted_and_trimmed_to_clip():
    transcript = make_transcript(
        (0, 2000, "앞"),
        (2500, 4000, "걸침"),
        (4000, 5000, "안"),
        (5500, 7000, "끝 걸침"),
    )
    clip = PlanClip(id="c1", video_id="v1", start_ms=3000, end_ms=6000)
    assert subtitle_events(clip, transcript) == [
        (0, 1000, "걸침"), (1000, 2000, "안"), (2500, 3000, "끝 걸침"),
    ]


def test_subtitle_events_without_transcript():
    clip = PlanClip(id="c1", video_id="v1", start_ms=0, end_ms=1000)
    assert subtitle_events(clip, None) == []


def test_edited_subtitles_are_split_by_clip():
    clips = (
        PlanClip(id="c0", video_id="v1", start_ms=10_000, end_ms=13_000),
        PlanClip(id="c1", video_id="v1", start_ms=50_000, end_ms=52_000),
    )
    subtitles = (
        PlanSubtitle(start_ms=500, end_ms=1500, text="첫 구간"),
        PlanSubtitle(start_ms=2500, end_ms=4000, text="경계에 걸침"),
        PlanSubtitle(start_ms=4200, end_ms=5000, text="둘째 구간"),
    )
    assert edited_subtitle_events(clips, subtitles) == [
        [(500, 1500, "첫 구간"), (2500, 3000, "경계에 걸침")],
        [(0, 1000, "경계에 걸침"), (1200, 2000, "둘째 구간")],
    ]


def test_plan_rejects_subtitle_longer_than_result():
    with pytest.raises(ValueError):
        make_plan((0, 2000), subtitles=(PlanSubtitle(start_ms=1500, end_ms=2500, text="초과"),))


def test_ass_time_and_text():
    assert _ass_time(0) == "0:00:00.00"
    assert _ass_time(3_723_450) == "1:02:03.45"
    assert _ass_text("{굵게}\\N 두  칸") == "(굵게)＼N 두 칸"


@pytest.mark.parametrize("style, expected", [
    (SubtitleStyle.BASIC, ",20,&H00FFFFFF,&H00000000,&H00000000,0,1,1.5,"),
    (SubtitleStyle.BOLD, ",26,&H00FFFFFF,&H00000000,&H00000000,-1,1,2.5,"),
    (SubtitleStyle.BOX, ",20,&H00000000,&H00FFFFFF,&H00FFFFFF,0,3,5,"),
])
def test_build_ass_applies_style(style, expected):
    ass = build_ass([(0, 1500, "안녕하세요")], style, "Malgun Gothic")
    style_line = next(line for line in ass.splitlines() if line.startswith("Style:"))
    assert "Malgun Gothic" in style_line
    assert expected in style_line
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,안녕하세요" in ass


def test_font_is_read_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SUBTITLE_FONT", raising=False)
    monkeypatch.setattr(ffmpeg, "dotenv_values", lambda path: {"SUBTITLE_FONT": "나눔고딕"})
    assert FFmpegVideoEditor().font == "나눔고딕"


def _has_ass_filter() -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    result = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return " ass " in result.stdout


needs_ffmpeg = pytest.mark.skipif(
    not DEMO.exists() or not _has_ass_filter(), reason="ffmpeg(libass) / demo.mp4 없음",
)


def _demo_video() -> VideoAsset:
    duration_ms, has_audio = probe_video(DEMO)
    return VideoAsset(
        id="v1", project_id="p1", filename="demo.mp4", source_path=Path("examples/demo.mp4"),
        duration_ms=duration_ms, sha256=hashlib.sha256(DEMO.read_bytes()).hexdigest(),
        has_audio=has_audio,
    )


@needs_ffmpeg
@pytest.mark.parametrize("style", list(SubtitleStyle))
def test_render_with_whisper_subtitles(tmp_path, monkeypatch, style):
    monkeypatch.chdir(DEMO.parents[1])
    transcript = make_transcript((0, 1500, "첫 번째 자막"), (1500, 3000, "두 번째 {자막}"))
    plan = make_plan((0, 1000), (1200, 2500), style=style)
    output = tmp_path / "out.mp4"

    result = FFmpegVideoEditor().render((_demo_video(),), (transcript,), plan, output)

    assert output.is_file() and output.stat().st_size > 0
    assert abs(result.duration_ms - 2300) < 200
    assert result.used_clip_ids == ("c0", "c1")


@needs_ffmpeg
def test_render_with_edited_subtitles(tmp_path, monkeypatch):
    monkeypatch.chdir(DEMO.parents[1])
    plan = make_plan((0, 1000), (1200, 2500), subtitles=(
        PlanSubtitle(start_ms=0, end_ms=2300, text="사용자가 고친 자막"),
    ))
    output = tmp_path / "out.mp4"

    result = FFmpegVideoEditor().render((_demo_video(),), (None,), plan, output)

    assert output.is_file() and abs(result.duration_ms - 2300) < 200