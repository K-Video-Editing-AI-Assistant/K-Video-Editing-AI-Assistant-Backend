# 담당 4 — 검색·추천: 내가 해야 할 일

[← 역할 목록](../ROLE_IMPLEMENTATION_MANUAL.md) · [키워드 추천 실습](../../RECOMMENDATION_WALKTHROUGH.md)

## 최종 목표

**사용자 요청에 맞는 자막을 골라 영상 구간·순서·추천 이유를 [RecommendationResult](../CONTRACT_SAMPLE_OUTPUTS.md#recommendationresult)로 반환**한다.

| 항목 | 내용 |
|---|---|
| **받는 입력** | [SearchRequest](../CONTRACT_SAMPLE_OUTPUTS.md#searchrequest), [Transcript](../CONTRACT_SAMPLE_OUTPUTS.md#transcript), [VideoAnalysis](../CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis) |
| **만들 결과** | [RecommendationResult](../CONTRACT_SAMPLE_OUTPUTS.md#recommendationresult) 안의 `clips: tuple[ClipSelection, ...]` ([ClipSelection 필드 정의](../INPUT_OUTPUT_CONTRACT_V1.md#model-clipselection)) |
| **그다음 사용처** | [Workflow](../MODULE_INTEGRATION_GUIDE.md)가 저장 → [PlanService](../INPUT_OUTPUT_CONTRACT_V1.md#io-plan-service)가 편집 초안 생성 → UI가 표시 |
| **공개 함수** | [`SegmentRecommender.recommend(...)`](../../src/video_assistant/core/interfaces.py) ([입출력 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-recommender)) |

## 수정할 곳

- 실제 구현: [`src/video_assistant/recommendation/llm.py`](../../src/video_assistant/recommendation/llm.py)
- 참고용: [`recommendation/stub.py`](../../src/video_assistant/recommendation/stub.py) (가짜), [`recommendation/keyword.py`](../../src/video_assistant/recommendation/keyword.py) (키워드 알고리즘)
- 새 테스트: `tests/contract/test_recommendation_llm_contract.py` (직접 만들 파일, 아직 링크 없음)

## 1단계 — 내 기능 구현·독립 테스트

1. **입력 확인:** [`tests/fixtures/contract_samples.py`](../../tests/fixtures/contract_samples.py)의 `sample_request()`, `sample_transcript()`, `sample_analysis()`를 읽고 [RecommendationResult 출력 예시](../CONTRACT_SAMPLE_OUTPUTS.md#recommendationresult)를 확인한다. 키워드 추천 참고 테스트는 기능 구현 후 연결 방법을 볼 때 사용한다.
2. `llm.py`에 `LLMSegmentRecommender(SegmentRecommender)`와 `VERSION`을 작성한다.
3. `request.query`, `transcript.segments`, `analysis.topics`에서 후보를 고른다. LLM을 쓰더라도 **구간 시간은 원본 자막 ID를 찾아 결정**한다.
4. 선택한 구간마다 `ClipSelection(id, start_ms, end_ms, reason, source_segment_ids)`를 만든다.
5. `RecommendationResult`에서 `request_id=request.id`, `transcript_id=transcript.id`, `analysis_id=analysis.id` 등 원본 참조를 유지해 반환한다.
6. Fixture로 `recommend()`를 **직접 호출**하는 테스트를 작성하고, 정상·추천 없음·실패·품질을 검증한다. 이때는 `bootstrap.py`를 수정하지 않는다.

## 2단계 — 기능이 준비되면 전체 흐름 테스트

1. 추천 기능이 준비되면 **자신의 브랜치에서** [`bootstrap.py`](../../src/video_assistant/bootstrap.py)의 `RECOMMENDERS`에 등록하고, 음성 인식·분석·편집은 Stub으로 두어 전체 흐름을 검증한다.
2. 독립/전체 흐름 테스트 결과와 등록 코드를 함께 PR로 제출한다.

## 선행 음성/분석이 없으면?

아래 입력 세 개를 바로 사용한다. **LLM 분석·Whisper를 실제 실행할 필요가 없다.**

```python
from tests.fixtures.contract_samples import sample_request, sample_transcript, sample_analysis

transcript = sample_transcript()
request = sample_request()
analysis = sample_analysis(transcript)

# 이제 담당자가 구현한 recommender.recommend(request, transcript, analysis)를 호출한다.
```

현재 예제 결과가 어떻게 전달되는지는 [`scripts/inspect_recommendation_flow.py`](../../scripts/inspect_recommendation_flow.py)를 `python scripts/inspect_recommendation_flow.py`로 실행해 볼 수 있다.

**개발 순서:** 독립 테스트를 먼저 완료한 뒤 전체 흐름 테스트로 진행합니다. [단계별 테스트 상세](../DEVELOPMENT_TEST_FLOW.md)

## 완료 체크

- [ ] 추천 없음은 오류가 아니라 `clips=()`로 반환한다.
- [ ] 추천 개수는 `request.max_clips` 이하, 시간은 영상 길이 이내다.
- [ ] 자막 참조 ID가 실존하며 `video_id`/`transcript_id`/`analysis_id`가 입력과 일치한다.
- [ ] 후보 선택 근거, 중복 처리, 재생 순서가 타당한지 실제 요청으로 평가한다.

**더 찾아보기:** [추천 계약 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-recommender) · [추천 결과 JSON](../CONTRACT_SAMPLE_OUTPUTS.md#recommendationresult) · [모듈 연결 가이드](../MODULE_INTEGRATION_GUIDE.md).
