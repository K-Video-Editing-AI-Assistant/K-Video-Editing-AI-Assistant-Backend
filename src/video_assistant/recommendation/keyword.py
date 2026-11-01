"""A small, working keyword recommender for learning the module contract.

This does not use an LLM or semantic embeddings. It is an intermediate
implementation that can be replaced by LLMSegmentRecommender later.
"""

from __future__ import annotations

import re
from uuid import uuid4

from video_assistant.core.errors import AppError, ErrorCode
from video_assistant.core.interfaces import SegmentRecommender
from video_assistant.core.models import (
    ClipSelection, RecommendationResult, SearchRequest, Transcript, VideoAnalysis,
)


class KeywordSegmentRecommender(SegmentRecommender):
    VERSION = "keyword-recommender-v1"

    def recommend(
        self, request: SearchRequest, transcript: Transcript, analysis: VideoAnalysis
    ) -> RecommendationResult:
        if request.video_id != transcript.video_id or analysis.video_id != request.video_id:
            raise AppError(ErrorCode.INVALID_INPUT, "영상 ID가 일치하지 않습니다.")
        if analysis.transcript_id != transcript.id:
            raise AppError(ErrorCode.INVALID_INPUT, "분석 결과의 자막 ID가 일치하지 않습니다.")

        terms = set(re.findall(r"[0-9a-z가-힣]+", request.query.casefold()))
        ranked = []
        for segment in transcript.segments:
            text = segment.text.casefold()
            score = sum(term in text for term in terms)
            for topic in analysis.topics:
                if segment.id in topic.segment_ids:
                    score += sum(term in topic.title.casefold() for term in terms)
            if score > 0:
                ranked.append((score, segment))

        ranked.sort(key=lambda item: (-item[0], item[1].start_ms))
        selected = ranked[:request.max_clips]
        clips = tuple(
            ClipSelection(
                id=uuid4().hex,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                reason=f"검색어와 일치하는 표현 {score}개가 발견되었습니다.",
                source_segment_ids=(segment.id,),
            )
            for score, segment in selected
        )

        return RecommendationResult(
            id=uuid4().hex,
            request_id=request.id,
            video_id=request.video_id,
            transcript_id=transcript.id,
            analysis_id=analysis.id,
            clips=clips,
            recommender_version=self.VERSION,
            is_stub=False,
        )
