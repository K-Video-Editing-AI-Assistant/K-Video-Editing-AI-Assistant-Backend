"""Minimal reusable Streamlit widgets (team 1 may expand)."""

from __future__ import annotations

import streamlit as st

from video_assistant.core.models import JobStatus, JobState


def job_status_card(job: JobStatus) -> None:
    label = f"{job.kind.value} · {job.state.value}"
    st.write(f"**{label}**")
    if job.stage:
        st.caption(f"단계: {job.stage.value}")
    st.progress((job.progress or 0) / 100)
    if job.state == JobState.FAILED:
        st.error(f"{job.error_code}: {job.error_message}")
    elif job.state == JobState.SUCCEEDED:
        st.success("작업 완료")
