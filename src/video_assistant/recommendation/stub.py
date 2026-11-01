"""Deterministic suggestion example, not actual semantic search."""

from uuid import uuid4

from video_assistant.core.interfaces import SegmentRecommender
from video_assistant.core.models import (
    ClipSelection, RecommendationResult, SearchRequest, Transcript, VideoAnalysis,
)


class StubSegmentRecommender(SegmentRecommender):
    VERSION = "stub-recommender-v1"

    def recommend(self, request: SearchRequest, transcript: Transcript, analysis: VideoAnalysis) -> RecommendationResult:
        no_results = any(term in request.query.lower() for term in ("검색 결과 없음", "추천 없음", "no results"))
        segments = [] if no_results else list(transcript.segments[:request.max_clips])
        clips = tuple(
            ClipSelection(
                id=uuid4().hex, start_ms=segment.start_ms, end_ms=segment.end_ms,
                reason="[데모] 검색과 무관한 고정 추천입니다.", source_segment_ids=(segment.id,),
            ) for segment in segments
        )
        return RecommendationResult(
            id=uuid4().hex, request_id=request.id, video_id=request.video_id,
            transcript_id=transcript.id, analysis_id=analysis.id, clips=clips,
            recommender_version=self.VERSION, is_stub=True,
        )
