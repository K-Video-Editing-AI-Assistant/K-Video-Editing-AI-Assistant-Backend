"""AI 담당자가 없어도 전체 데이터 흐름을 테스트할 수 있는 고정 구현.

이 구현은 실제 자막의 의미를 이해하거나 LLM을 호출하지 않습니다.
"""

from core.interfaces import (
    ContentAnalyzer, ProjectAnalyzer, SegmentRecommender, TranscriptPreprocessor,
)
from core.models import (
    KeywordSuggestion, ProcessedSegment, ProcessedTranscript, Project,
    ProjectAnalysis, RecommendationClip, RecommendationResult, RecommendedTopic,
    SearchRequest, TopicSection, Transcript, VideoAnalysis, new_id,
)


class StubPreprocessor(TranscriptPreprocessor):
    VERSION = "stub-preprocessor-v1"

    def preprocess(self, transcript: Transcript) -> ProcessedTranscript:
        """원본 자막의 ID와 타임스탬프를 보존하면서 형식만 변환합니다."""
        segments = tuple(
            ProcessedSegment(
                id=new_id(), start_ms=s.start_ms, end_ms=s.end_ms,
                text=s.text, source_segment_ids=(s.id,),
            ) for s in transcript.segments
        )
        return ProcessedTranscript(
            id=new_id(), video_id=transcript.video_id, source_transcript_id=transcript.id,
            segments=segments, preprocessing_version=self.VERSION, is_stub=True,
        )


class StubContentAnalyzer(ContentAnalyzer):
    VERSION = "stub-content-analyzer-v1"

    def analyze(self, transcript: ProcessedTranscript) -> VideoAnalysis:
        """각 전처리 발언을 데모 주제로 만들며 원본 발언 참조를 유지합니다."""
        topics = tuple(
            TopicSection(
                id=new_id(), title="테스트 주제: AI 활용",
                description="이 주제는 실제 AI 분석 결과가 아닙니다.",
                start_ms=seg.start_ms, end_ms=seg.end_ms,
                source_segment_ids=seg.source_segment_ids,
            ) for seg in transcript.segments
        )
        return VideoAnalysis(
            id=new_id(), video_id=transcript.video_id,
            transcript_id=transcript.source_transcript_id, processed_transcript_id=transcript.id,
            summary="[Stub] 테스트용 영상 내용 요약입니다." if topics else "",
            topics=topics, analyzer_version=self.VERSION, is_stub=True,
        )


class StubProjectAnalyzer(ProjectAnalyzer):
    VERSION = "stub-project-analyzer-v1"

    def analyze_project(
        self, project: Project, analyses: tuple[VideoAnalysis, ...],
    ) -> ProjectAnalysis:
        """영상별 AI 분석을 프로젝트에 묶어 테스트 검색 키워드를 만듭니다."""
        topic_ids = tuple(topic.id for item in analyses for topic in item.topics)
        keywords = (
            KeywordSuggestion(keyword="AI 활용", reason="[Stub] 테스트용 키워드",
                              topic_ids=topic_ids),
        ) if topic_ids else ()
        return ProjectAnalysis(
            id=new_id(), project_id=project.id,
            video_analysis_ids=tuple(item.id for item in analyses),
            suggested_keywords=keywords,
        )


class StubSegmentRecommender(SegmentRecommender):
    VERSION = "stub-recommender-v1"

    def recommend(
        self, request: SearchRequest, transcripts: tuple[Transcript, ...],
        analyses: tuple[VideoAnalysis, ...], project_analysis: ProjectAnalysis,
    ) -> RecommendationResult:
        """각 원본 영상의 앞쪽 구간을 골라 테스트 추천을 만듭니다."""
        by_id = {transcript.video_id: transcript for transcript in transcripts}
        selected = []
        for video_id in request.video_ids:
            transcript = by_id[video_id]
            for segment in transcript.segments:
                if len(selected) >= request.max_clips:
                    break
                selected.append(RecommendationClip(
                    id=new_id(), video_id=video_id, start_ms=segment.start_ms,
                    end_ms=segment.end_ms, reason="[Stub] 검색 의미와 무관한 테스트 추천",
                    source_segment_ids=(segment.id,),
                ))
        clips = tuple(selected)
        topics = (
            RecommendedTopic(id=new_id(), title="[Stub] 추천 주제",
                             description="테스트용 분류", clip_ids=tuple(clip.id for clip in clips)),
        ) if clips else ()
        return RecommendationResult(
            id=new_id(), project_id=request.project_id, request_id=request.id,
            project_analysis_id=project_analysis.id, clips=clips, topics=topics,
            suggested_title="[Stub] 추천 결과", recommender_version=self.VERSION,
            is_stub=True,
        )
