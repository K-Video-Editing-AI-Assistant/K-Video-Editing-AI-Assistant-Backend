"""AI-01~04를 단독 실행하는 진단 스크립트.

기본값: API 호출 없는 규칙 기반 연결 점검.
--live: 사용자 PC에서 .env의 Gemini 키를 사용해 실제 API 호출(요금 발생 가능).
"""

import argparse
from dataclasses import replace

from ai.analyzer import LLMContentAnalyzer, LLMProjectAnalyzer
from ai.config import AIProvider, AISettings
from ai.preprocessing import AITranscriptPreprocessor
from ai.recommender import LLMSegmentRecommender
from core.models import Project, SearchRequest, Transcript, TranscriptSegment, new_id


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-01~04 독립 파이프라인 확인")
    parser.add_argument("--live", action="store_true", help="실제 Gemini API를 호출합니다 (요금이 발생할 수 있음)")
    args = parser.parse_args()

    base = AISettings.from_env()
    provider = AIProvider.GEMINI if args.live else AIProvider.RULE_BASED
    settings = replace(base, provider=provider)

    project = Project(id=new_id(), title="AI 기능 검증", video_ids=())
    transcript = Transcript(
        id=new_id(), video_id=new_id(), transcriber_version="manual-fixture-v1",
        segments=(
            TranscriptSegment(id=new_id(), start_ms=0, end_ms=2200, text="AI가 일상 업무를 자동화하고 생산성을 높여줍니다."),
            TranscriptSegment(id=new_id(), start_ms=2400, end_ms=4500, text="반복적인 문서 정리는 AI 활용의 대표적인 예시입니다."),
            TranscriptSegment(id=new_id(), start_ms=5000, end_ms=7100, text="하지만 중요한 결정에는 사람의 검토가 필요합니다."),
        ),
    )
    project = project.model_copy(update={"video_ids": (transcript.video_id,)})
    request = SearchRequest(
        id=new_id(), project_id=project.id, video_ids=(transcript.video_id,),
        query="AI를 활용해 업무 생산성을 높이는 부분만 추천해줘", max_clips=3,
    )

    print("실행 모드:", provider.value)
    if args.live:
        print("Gemini 모델:", settings.gemini_model)
        print("주의: 테스트용 자막이 외부 Gemini API로 전송되며 요금이 발생할 수 있습니다.")

    processed = AITranscriptPreprocessor(settings=settings).preprocess(transcript)
    print("\n[AI-01]", processed.preprocessing_version)
    print("정리 자막:", [segment.text for segment in processed.segments])

    analysis = LLMContentAnalyzer(settings=settings).analyze(processed)
    print("\n[AI-02]", analysis.analyzer_version)
    print("요약:", analysis.summary)
    print("주제:", [(topic.title, topic.start_ms, topic.end_ms) for topic in analysis.topics])

    project_analysis = LLMProjectAnalyzer(settings=settings).analyze_project(project, (analysis,))
    print("\n[AI-03] 추천 키워드:", [keyword.keyword for keyword in project_analysis.suggested_keywords])

    result = LLMSegmentRecommender(settings=settings).recommend(
        request, (transcript,), (analysis,), project_analysis,
    )
    print("\n[AI-04]", result.recommender_version)
    print("제목:", result.suggested_title)
    print("클립:", [(clip.start_ms, clip.end_ms, clip.reason) for clip in result.clips])

    if args.live and ("gemini-fallback" in processed.preprocessing_version
                      or "gemini-fallback" in analysis.analyzer_version
                      or "gemini-fallback" in result.recommender_version):
        print("\n경고: 일부 AI 단계가 규칙 기반으로 대체되었습니다. 로그를 확인하세요.")
        return 1

    print("\nCore 데이터 계약을 유지한 AI 연결 점검이 완료되었습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
