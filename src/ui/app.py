"""UI 담당자: minimal working Streamlit proof of the shared application contract.

This is a functional development screen, NOT the final CLIPNOTE design mockup.
It calls only ApplicationService methods, never Whisper/LLM/FFmpeg directly.
"""

import streamlit as st

from bootstrap import create_application
from core.errors import AppError, ErrorCode
from core.models import (
    EditMode, JobState, PlanClip, PlanStatus, SearchRequest, SubtitleStyle, new_id,
)

st.set_page_config(page_title="CLIPNOTE 개발 스켈레톤", layout="wide")
st.title("CLIPNOTE · 기능 연결 확인")
st.caption("5인 역할 기반 단일 Python 앱 · 현재 UI는 최종 디자인이 아닌 개발 검증용입니다.")
st.info("기본 모드는 모두 Stub입니다. 자막/AI 결과는 테스트 데이터이며 Stub 편집기는 첫 영상을 복사합니다.")


@st.cache_resource
def get_service():
    return create_application()


app = get_service()
for key in ("project_id", "prepare_job", "recommend_job", "render_job", "recommendation_id"):
    st.session_state.setdefault(key, None)


def job_status(state_key: str):
    job_id = st.session_state[state_key]
    if not job_id:
        return None
    try:
        job = app.get_job(job_id)
    except Exception as exc:
        st.error(f"작업 상태 조회 실패: {exc}")
        return None
    if job.state in (JobState.QUEUED, JobState.RUNNING):
        st.info(f"{job.kind.value} 작업 진행: {job.state.value} ({job.progress}%)")
    elif job.state == JobState.FAILED:
        st.error(f"{job.kind.value} 작업 실패: {job.error_message}")
    return job


if st.button("작업 상태 새로고침"):
    st.rerun()

st.subheader("1 · 프로젝트와 원본 영상")
if not st.session_state.project_id and st.button("새 프로젝트 만들기"):
    try:
        project = app.create_project("CLIPNOTE 편집 프로젝트")
        st.session_state.project_id = project.id
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

project_id = st.session_state.project_id
project = None
if project_id:
    try:
        project = app.get_project(project_id)
    except Exception as exc:
        st.error(f"프로젝트를 불러올 수 없습니다: {exc}")

if project:
    st.caption(f"프로젝트 ID: {project.id}")
    files = st.file_uploader("원본 MP4 추가 (여러 개 가능)", type=["mp4"], accept_multiple_files=True)
    if st.button("선택한 영상 등록", disabled=not files):
        try:
            for source in files:
                app.add_video(project.id, source.name, source.getvalue())
            st.success(f"영상 {len(files)}개 등록")
            st.rerun()
        except Exception as exc:
            st.error(f"업로드 실패: {exc}")
    project = app.get_project(project.id)
    videos = [app.get_video(project.id, vid) for vid in project.video_ids]
    for index, video in enumerate(videos, 1):
        st.write(f"{index}. {video.filename} — {video.duration_ms / 1000:.2f}초")
else:
    videos = []

st.subheader("2 · Whisper → AI 분석")
if st.button("영상 준비 시작", disabled=not videos):
    try:
        job = app.submit_prepare(project.id)
        st.session_state.prepare_job = job.id
        st.session_state.recommend_job = None
        st.session_state.recommendation_id = None
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

prepare_job = job_status("prepare_job")
project_analysis = None
if project:
    try:
        project_analysis = app.get_project_analysis(project.id)
        st.write("추천 키워드:", [item.keyword for item in project_analysis.suggested_keywords])
        for video in videos:
            analysis = app.get_video_analysis(project.id, video.id)
            transcript = app.get_transcript(project.id, video.id)
            with st.expander(f"{video.filename} · 요약 및 자막", expanded=False):
                st.write(analysis.summary)
                st.write([f"{s.start_ms}~{s.end_ms}ms: {s.text}" for s in transcript.segments])
    except AppError as exc:
        if exc.code != ErrorCode.NOT_FOUND:
            st.warning(str(exc))

st.subheader("3 · 자연어 구간 추천")
query = st.text_input("요청 문장", value="AI 활용과 생산성에 관련된 장면만 모아줘")
edit_mode = st.selectbox("편집 순서 정책", list(EditMode), format_func=lambda x: x.value)
if st.button("추천 요청", disabled=project_analysis is None or not query.strip()):
    try:
        request = SearchRequest(
            id=new_id(), project_id=project.id, video_ids=project.video_ids,
            query=query.strip(), edit_mode=edit_mode,
        )
        job = app.submit_recommend(request)
        st.session_state.recommend_job = job.id
        st.session_state.recommendation_id = None
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

recommend_job = job_status("recommend_job")
if recommend_job and recommend_job.state == JobState.SUCCEEDED:
    st.session_state.recommendation_id = recommend_job.result_ref
recommendation = None
if project and st.session_state.recommendation_id:
    try:
        recommendation = app.get_recommendation(project.id, st.session_state.recommendation_id)
        for index, clip in enumerate(recommendation.clips, 1):
            st.write(f"{index}. {clip.video_id[:8]} · {clip.start_ms}~{clip.end_ms}ms · {clip.reason}")
        if not recommendation.clips:
            st.warning("추천 결과가 없습니다. 다른 요청을 입력하세요.")
        style = st.selectbox("자막 스타일(계획에 저장)", list(SubtitleStyle), format_func=lambda x: x.value)
        if st.button("추천 결과를 편집 초안으로 만들기", disabled=not recommendation.clips):
            app.create_plan(project.id, recommendation.id, style)
            st.rerun()
    except Exception as exc:
        st.error(str(exc))

st.subheader("4 · 편집 계획 검토·승인")
plan = None
if project:
    try:
        plan = app.get_plan(project.id)
    except AppError as exc:
        if exc.code != ErrorCode.NOT_FOUND:
            st.error(str(exc))
if plan:
    st.caption(f"편집 계획 {plan.id[:8]} · v{plan.version} · {plan.status.value}")
    if plan.status == PlanStatus.DRAFT:
        with st.form(f"plan_{plan.id}_{plan.version}"):
            edits = []
            for index, clip in enumerate(plan.clips):
                st.write(f"클립 {index + 1} · 원본 {clip.video_id[:8]}")
                a, b, c, d = st.columns(4)
                start = a.number_input("시작(ms)", value=clip.start_ms, min_value=0,
                                       key=f"start_{plan.version}_{index}")
                end = b.number_input("종료(ms)", value=clip.end_ms, min_value=1,
                                     key=f"end_{plan.version}_{index}")
                order = c.number_input("순서", value=index + 1, min_value=1,
                                       key=f"order_{plan.version}_{index}")
                include = d.checkbox("포함", value=True, key=f"include_{plan.version}_{index}")
                if include:
                    edits.append((order, index, clip, int(start), int(end)))
            save = st.form_submit_button("변경 적용")
            if save:
                try:
                    updated_clips = tuple(
                        PlanClip.model_validate({**clip.model_dump(), "start_ms": start, "end_ms": end})
                        for _, _, clip, start, end in sorted(edits, key=lambda x: (x[0], x[1]))
                    )
                    app.revise_plan(project.id, plan.id, plan.version, updated_clips)
                    st.rerun()
                except Exception as exc:
                    st.error(f"계획 수정 실패: {exc}")
        if st.button("계획 승인", disabled=not plan.clips):
            try:
                app.approve_plan(project.id, plan.id, plan.version)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        if st.button("승인한 계획으로 렌더링"):
            try:
                job = app.submit_render(project.id, plan.id, plan.version)
                st.session_state.render_job = job.id
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

st.subheader("5 · 결과")
render_job = job_status("render_job")
if project and render_job and render_job.state == JobState.SUCCEEDED:
    try:
        result = app.get_render_result(project.id)
        if result.is_stub:
            st.warning("Stub 렌더링입니다. 실제 클립 추출 대신 첫 번째 원본 영상을 복사했습니다.")
        else:
            st.caption("FFmpeg 기본 컷 편집 결과입니다. 자막 합성은 아직 지원하지 않습니다.")
        st.video(str(result.output_path))
        st.download_button("결과 다운로드", result.output_path.read_bytes(),
                           file_name="clipnote_result.mp4", mime="video/mp4")
    except Exception as exc:
        st.error(f"결과 조회 실패: {exc}")
