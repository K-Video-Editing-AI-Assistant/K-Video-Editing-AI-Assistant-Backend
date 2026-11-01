# 담당 1 — UI/UX: 내가 해야 할 일

[← 역할 목록](../ROLE_IMPLEMENTATION_MANUAL.md) · [실행 방법](../SETUP_AND_RUN.md)

## 최종 목표

사용자가 **영상 업로드 → 분석 대기 → 검색·추천 → 계획 수정·승인 → 결과 재생/다운로드**를 한 화면 흐름으로 진행하도록 만든다.

## 내가 받는 것 / 전달하는 것

- **입력:** 사용자 MP4·검색어·수정한 구간; [`ApplicationService`](../../src/video_assistant/core/interfaces.py)를 통해 [JobStatus 필드](../INPUT_OUTPUT_CONTRACT_V1.md#model-jobstatus), [Transcript](../CONTRACT_SAMPLE_OUTPUTS.md#transcript), [VideoAnalysis](../CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis), [RecommendationResult](../CONTRACT_SAMPLE_OUTPUTS.md#recommendationresult), [EditPlan](../CONTRACT_SAMPLE_OUTPUTS.md#editplan), [RenderResult](../CONTRACT_SAMPLE_OUTPUTS.md#renderresult)를 조회.
- **내 역할:** 결과를 화면에 표시하고 사용자 입력을 공통 서비스로 전달한다.
- **다음 단계:** [`ApplicationService`](../../src/video_assistant/core/interfaces.py)가 작업을 등록하고 [Workflow](../MODULE_INTEGRATION_GUIDE.md)가 해당 기능을 호출한다. UI가 다른 모듈을 직접 호출하지 않는다.

## 내가 수정할 파일

- [`src/video_assistant/ui/app.py`](../../src/video_assistant/ui/app.py) — Streamlit 화면/작업 상태/호출
- [`src/video_assistant/ui/components.py`](../../src/video_assistant/ui/components.py) — 재사용 UI 요소
- 새 테스트: `tests/unit/test_ui_*.py` (필요 시 추가)

## 1단계 — 내 기능 구현·독립 테스트

1. **화면을 먼저 실행한다.** [설치·실행](../SETUP_AND_RUN.md)대로 네 백엔드를 모두 Stub으로 둔다.
2. **현재 화면의 흐름을 읽는다.** [UI 공개 함수 계약](../INPUT_OUTPUT_CONTRACT_V1.md#io-ui)을 참고하여 `app.ingest()`, `app.submit_prepare()`, `app.submit_recommend()`, `app.create_plan()`, `app.approve_plan()`, `app.submit_render()` 호출 위치를 찾는다.
3. **결과 표시를 보완한다.** [각 결과 JSON](../CONTRACT_SAMPLE_OUTPUTS.md)을 참고하여 `get_job()`, `get_transcript()`, `get_analysis()`, `get_recommendation()`, `get_render_result()`로 조회한 데이터를 화면에 나타낸다.
4. **오류·빈 결과를 구분한다.** 작업 실패, 무음 자막, 추천 없음, 승인 불가 등의 상태를 표시한다.
5. **독립 UI 테스트:** 다른 모듈을 모두 Stub으로 유지하고 화면 동작, 진행 상태, 빈 결과/오류 표현을 테스트한다. UI는 `bootstrap.py`를 수정할 필요가 없다.

## 2단계 — 기능이 준비되면 전체 흐름 테스트

1. **UI 기능이 준비된 뒤 전체 흐름 테스트:** 실제 구현이 제공되는 모듈부터 함께 선택해 화면부터 결과 다운로드까지 확인한다.
2. **Stub과 Real을 구분해 보여준다.** `is_stub`이 참이면 실제 AI 결과나 실제 편집이라고 주장하지 않는다. 이후 PR을 제출한다.

**개발 순서:** 독립 테스트를 먼저 완료한 뒤 전체 흐름 테스트로 진행합니다. [단계별 테스트 상세](../DEVELOPMENT_TEST_FLOW.md)

## 완료 체크

- [ ] `examples/demo.mp4`로 업로드부터 Stub 결과 다운로드까지 가능하다.
- [ ] 없는 추천·실패 상태·오류 메시지에 화면이 깨지지 않는다.
- [ ] 계획 검증·승인을 UI에서 임의로 구현하지 않고 서비스에 위임한다.
- [ ] 백그라운드 작업에서 Streamlit API를 호출하지 않는다.

**더 찾아보기:** [UI 서비스 호출 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-ui) · [전체 흐름](../ARCHITECTURE.md) · [실제 인터페이스 코드](../../src/video_assistant/core/interfaces.py).
