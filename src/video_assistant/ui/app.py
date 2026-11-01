"""Minimal functional UI: upload -> prepare -> recommend -> edit -> approve -> download."""

from __future__ import annotations

from uuid import uuid4

import streamlit as st
from pydantic import ValidationError

from video_assistant.bootstrap import create_application
from video_assistant.core.errors import AppError
from video_assistant.core.models import ClipSelection, JobState, PlanStatus, SearchRequest
from video_assistant.ui.components import job_status_card

st.set_page_config(page_title="AI 영상편집 어시스턴트 스켈레톤", layout="wide")
st.title("AI 영상편집 어시스턴트 — Stub 데모")
st.warning("현재 모든 AI 모듈은 더미입니다. 자막·분석·추천은 실제 영상과 무관하며, 출력 영상은 승인한 구간으로 편집되지 않고 원본이 그대로 복사됩니다.")


@st.cache_resource
def app_service():
    return create_application()


app = app_service()


def run_action(action):
    try:
        return action()
    except (AppError, ValidationError, OSError) as exc:
        st.error(str(exc))
        return None


def clear_downstream() -> None:
    for key in (
        "prepare_job", "recommend_job", "render_job", "recommendation_id",
        "plan_id", "render_result_id",
    ):
        st.session_state.pop(key, None)


def sync_completed_jobs() -> None:
    for key, result_key in (
        ("recommend_job", "recommendation_id"),
        ("render_job", "render_result_id"),
    ):
        job_id = st.session_state.get(key)
        if job_id:
            status = app.get_job(job_id)
            if status.state == JobState.SUCCEEDED:
                st.session_state[result_key] = status.result_ref


@st.fragment(run_every="2s")
def job_monitor() -> None:
    pending = False
    seen = st.session_state.setdefault("seen_terminal_jobs", set())
    for key in ("prepare_job", "recommend_job", "render_job"):
        job_id = st.session_state.get(key)
        if not job_id:
            continue
        job = app.get_job(job_id)
        job_status_card(job)
        if job.state in (JobState.QUEUED, JobState.RUNNING):
            pending = True
        if job.state in (JobState.SUCCEEDED, JobState.FAILED) and job_id not in seen:
            seen.add(job_id)
            st.rerun()  # Refresh full UI when a background job finishes.
    if pending:
        st.caption("2초마다 상태를 갱신합니다.")


st.header("1. 영상 업로드")
uploaded = st.file_uploader("MP4 파일을 업로드하세요", type=["mp4"])
if st.button("영상 등록", disabled=uploaded is None):
    video = run_action(lambda: app.ingest(uploaded.name, uploaded))
    if video is not None:
        clear_downstream()
        st.session_state["video_id"] = video.id
        st.rerun()

video_id = st.session_state.get("video_id")
if not video_id:
    st.info("데모를 시작하려면 examples/demo.mp4를 업로드하세요.")
    st.stop()

video = app.get_video(video_id)
st.caption(f"등록: {video.original_name} · {video.duration_ms / 1000:.2f}초 · ID: {video.id[:8]}")

st.header("2. 자막 생성과 영상 분석")
if st.button("영상 준비 작업 시작"):
    job = run_action(lambda: app.submit_prepare(video_id))
    if job:
        st.session_state["prepare_job"] = job.id
        st.rerun()

sync_completed_jobs()
job_monitor()

transcript = app.get_transcript(video_id)
analysis = app.get_analysis(video_id)
if transcript and analysis:
    st.success("저장된 자막 및 분석 결과를 재사용할 수 있습니다.")
    with st.expander("자막 내용", expanded=True):
        for segment in transcript.segments:
            st.write(f"{segment.start_ms / 1000:.2f}–{segment.end_ms / 1000:.2f}초: {segment.text}")
        if not transcript.segments:
            st.write("음성 자막이 없습니다.")
    st.write("**영상 요약:**", analysis.summary or "요약할 자막이 없습니다.")

st.header("3. 자연어 검색 및 구간 추천")
with st.form("recommendation_form"):
    query = st.text_input("요청", value="AI 활용 사례만 모아줘")
    max_clips = st.slider("최대 추천 구간", min_value=1, max_value=10, value=3)
    submitted = st.form_submit_button("구간 추천 요청", disabled=analysis is None)
if submitted:
    def submit_recommend():
        request = SearchRequest(id=uuid4().hex, video_id=video_id, query=query, max_clips=max_clips)
        return app.submit_recommend(request)

    job = run_action(submit_recommend)
    if job:
        for key in ("recommendation_id", "plan_id", "render_result_id", "render_job"):
            st.session_state.pop(key, None)
        st.session_state["recommend_job"] = job.id
        st.rerun()

recommendation_id = st.session_state.get("recommendation_id")
if recommendation_id:
    recommendation = app.get_recommendation(recommendation_id)
    st.write(f"추천 구간 {len(recommendation.clips)}개")
    for clip in recommendation.clips:
        st.write(f"{clip.start_ms / 1000:.2f}–{clip.end_ms / 1000:.2f}초: {clip.reason}")
    if st.button("추천 결과로 편집 계획 생성"):
        plan = run_action(lambda: app.create_plan(recommendation_id))
        if plan:
            st.session_state["plan_id"] = plan.id
            st.session_state.pop("render_result_id", None)
            st.rerun()

plan_id = st.session_state.get("plan_id")
if plan_id:
    st.header("4. 편집 계획 수정 및 승인")
    plan = app.get_plan(plan_id)
    st.write(f"계획 버전: {plan.version} / 상태: {plan.status.value}")
    if plan.status == PlanStatus.DRAFT:
        with st.form(f"edit_plan_{plan.id}_{plan.version}"):
            edits = []
            for i, clip in enumerate(plan.clips):
                st.markdown(f"**클립 {i + 1}** — {clip.reason}")
                cols = st.columns([1, 2, 2, 2])
                with cols[0]:
                    include = st.checkbox("포함", value=True, key=f"include_{plan.version}_{clip.id}")
                with cols[1]:
                    order = st.number_input("순서", min_value=1, max_value=max(1, len(plan.clips)), value=i + 1, key=f"order_{plan.version}_{clip.id}")
                with cols[2]:
                    start = st.number_input("시작(초)", min_value=0.0, value=clip.start_ms / 1000, step=0.1, key=f"start_{plan.version}_{clip.id}")
                with cols[3]:
                    end = st.number_input("종료(초)", min_value=0.0, value=clip.end_ms / 1000, step=0.1, key=f"end_{plan.version}_{clip.id}")
                if include:
                    edits.append((order, i, clip, start, end))
            save = st.form_submit_button("수정 내용 저장")
        if save:
            def revise():
                clips = tuple(
                    ClipSelection(
                        id=clip.id, start_ms=round(start * 1000), end_ms=round(end * 1000),
                        reason=clip.reason, source_segment_ids=clip.source_segment_ids,
                    ) for _, _, clip, start, end in sorted(edits, key=lambda entry: (entry[0], entry[1]))
                )
                return app.revise_plan(plan.id, plan.version, clips)

            updated = run_action(revise)
            if updated:
                st.rerun()
        if st.button("현재 계획 승인", disabled=not plan.clips):
            approved = run_action(lambda: app.approve_plan(plan.id, plan.version))
            if approved:
                st.rerun()
    else:
        st.success("최신 계획이 승인되었습니다.")
        if st.button("영상 결과 생성"):
            job = run_action(lambda: app.submit_render(plan.id, plan.version))
            if job:
                st.session_state["render_job"] = job.id
                st.session_state.pop("render_result_id", None)
                st.rerun()

result_id = st.session_state.get("render_result_id")
if result_id:
    st.header("5. 결과 영상")
    result = app.get_render_result(result_id)
    if result.is_stub:
        st.warning("Stub 편집 결과: 편집 계획이 적용되지 않았습니다. 원본 MP4의 복사본입니다.")
    with result.output_path.open("rb") as file:
        st.video(file.read())
    with result.output_path.open("rb") as file:
        st.download_button("결과 영상 다운로드", data=file, file_name="stub_output.mp4", mime="video/mp4")
