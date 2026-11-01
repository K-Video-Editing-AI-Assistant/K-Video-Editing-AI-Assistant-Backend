# 담당 3 — 영상 내용 분석: 내가 해야 할 일

[← 역할 목록](../ROLE_IMPLEMENTATION_MANUAL.md)

## 최종 목표

**자막 내용을 요약하고 주제를 분류해 [VideoAnalysis](../CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis) 객체를 반환**한다. 사용자의 검색 요청에 따른 추천은 만들지 않는다.

| 항목 | 내용 |
|---|---|
| **받는 입력** | [Transcript](../CONTRACT_SAMPLE_OUTPUTS.md#transcript) (자막 ID, 문장, 시간, 언어) |
| **만들 결과** | [VideoAnalysis](../CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis) (요약, 주제 구간 [TopicSection 예시](../CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis), 자막 참조 ID) |
| **그다음 사용처** | [추천 모듈](recommendation.md)의 후보 탐색, [UI](ui.md)의 요약/주제 표시 |
| **공개 함수** | [`ContentAnalyzer.analyze(...)`](../../src/video_assistant/core/interfaces.py) ([입출력 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-analyzer)) |

## 수정할 곳

- 실제 구현: [`src/video_assistant/analysis/llm.py`](../../src/video_assistant/analysis/llm.py)
- 참고: [`analysis/stub.py`](../../src/video_assistant/analysis/stub.py), [`analysis/simple.py`](../../src/video_assistant/analysis/simple.py) (연습용 규칙 기반)
- 새 테스트: `tests/contract/test_analysis_llm_contract.py` (직접 만들 파일, 아직 링크 없음)

## 1단계 — 내 기능 구현·독립 테스트

1. [`ContentAnalyzer` 인터페이스](../../src/video_assistant/core/interfaces.py)와 [VideoAnalysis·TopicSection 예시](../CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis)를 확인한다.
2. `LLMContentAnalyzer(ContentAnalyzer)`와 `VERSION`을 만든다.
3. `Transcript.segments`를 분석하여 전체 요약과 소주제별 **실제 자막 ID** 목록을 만든다.
4. 주제별 시작/종료 시간을 원본 자막에서 계산하고, `video_id=transcript.video_id`, `transcript_id=transcript.id`를 유지한 결과를 반환한다.
5. `sample_transcript()`로 `analyze()`를 **직접 호출**해 정상·빈 결과·실패를 먼저 테스트한다. `bootstrap.py` 등록은 필요 없다.

## 2단계 — 기능이 준비되면 전체 흐름 테스트

1. 기능이 준비되면 **자신의 브랜치에서** [`bootstrap.py`](../../src/video_assistant/bootstrap.py)의 `ANALYZERS`에 등록해 다른 모듈의 Stub과 전체 흐름을 검사한다.
2. 독립·통합 테스트 결과와 함께 PR을 제출한다.

## 선행 음성 인식이 없으면?

[`tests/fixtures/contract_samples.py`](../../tests/fixtures/contract_samples.py)의 `sample_transcript()`를 입력으로 사용한다. 또는 StubTranscriber의 결과를 써도 된다. 실제 Whisper 개발을 기다릴 이유가 없다.

**개발 순서:** 독립 테스트를 먼저 완료한 뒤 전체 흐름 테스트로 진행합니다. [단계별 테스트 상세](../DEVELOPMENT_TEST_FLOW.md)

## 완료 체크

- [ ] 빈 자막을 처리할 수 있다 (`summary=""`, `topics=()` 허용).
- [ ] 주제가 참조하는 모든 `segment_ids`가 입력 자막에 실제로 존재한다.
- [ ] `video_id`, `transcript_id`, `analyzer_version`이 정확하다.
- [ ] API 실패/비정상 LLM 결과를 별도로 처리하고, 실제 요약 품질을 평가한다.

**더 찾아보기:** [내용 분석 계약 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-analyzer) · [VideoAnalysis JSON](../CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis) · [공통 모델 정의](../../src/video_assistant/core/models.py).
