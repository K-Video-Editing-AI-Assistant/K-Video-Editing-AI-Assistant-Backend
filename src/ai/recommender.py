"""AI 담당자: 검색어에 맞는 다중 영상 클립 추천의 실제 구현 위치."""

from core.interfaces import SegmentRecommender
from core.models import (
    ProjectAnalysis, RecommendationResult, SearchRequest, Transcript, VideoAnalysis,
)


class LLMSegmentRecommender(SegmentRecommender):
    VERSION = "recommender-unimplemented"

    def recommend(
        self, request: SearchRequest, transcripts: tuple[Transcript, ...],
        analyses: tuple[VideoAnalysis, ...], project_analysis: ProjectAnalysis,
    ) -> RecommendationResult:
        raise NotImplementedError("AI 구간 추천 담당자가 구현해야 합니다.")
