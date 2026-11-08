# 5인 담당자별 작업 가이드

각 담당자는 먼저 **독립 구현·독립 테스트**를 완료하고, 준비된 후 전체 Stub 흐름에 연결합니다.

## PM — 공통 계약 관리

- **수정 위치:** [`core/models.py`](../src/core/models.py), [`core/interfaces.py`](../src/core/interfaces.py), [`core/errors.py`](../src/core/errors.py), `docs/`.
- **할 일:** 다중 영상 ID, 시간 단위, 승인·오류 계약을 검토·관리하고 영향을 받는 담당자와 조율합니다.
- **완료:** 계약 변경 시 관련 Fixture, Stub, Application 검증 테스트가 함께 변경되었는지 확인합니다.

## UI 담당 — Streamlit

- **수정 위치:** [`ui/app.py`](../src/ui/app.py); 필요하면 `ui/components/` 등을 추가.
- **받는 데이터:** `Project`, `JobStatus`, `VideoAnalysis`, `ProjectAnalysis`, `RecommendationResult`, `EditPlan`, `RenderResult`.
- **할 일:** 화면·파일 입력·검색어 입력·추천 검토·계획 수정/승인·결과 다운로드. 단, 서비스 메서드만 호출합니다.
- **독립 테스트:** ApplicationService Stub/Fixture로 표시·입력 검증. **전체 테스트:** Streamlit에서 업로드부터 다운로드 확인.

## AI 영상분석 담당

- **수정 위치:** [`ai/preprocessing.py`](../src/ai/preprocessing.py), [`ai/analyzer.py`](../src/ai/analyzer.py), [`ai/recommender.py`](../src/ai/recommender.py).
- **받는 데이터:** [`Transcript`, `ProcessedTranscript`, `SearchRequest`](INPUT_OUTPUT_CONTRACT.md).
- **반환:** [`ProcessedTranscript`, `VideoAnalysis`, `ProjectAnalysis`, `RecommendationResult`](INPUT_OUTPUT_CONTRACT.md).
- **할 일:** 전처리, 영상별 요약/주제, 전체 키워드, 요청별 관련 클립·추천 이유 작성.
- **독립 테스트:** `tests/fixtures/contract_samples.py`로 공개 메서드 직접 호출, 빈 자막·ID 일치·시간 확인.
- **전체 테스트:** `bootstrap.py`에 단계별 구현 등록 후 나머지 모듈 Stub으로 실행.

## 영상처리 담당

- **수정 위치:** [`processing/files.py`](../src/processing/files.py), [`processing/whisper.py`](../src/processing/whisper.py), [`processing/ffmpeg.py`](../src/processing/ffmpeg.py).
- **받는 데이터:** MP4, `VideoAsset`, `ApprovedEditPlan`, 자막 목록.
- **반환:** `VideoAsset`, `Transcript`, `RenderResult` 및 MP4/SRT 파일.
- **할 일:** 파일 검증·저장·Whisper 음성 인식·FFmpeg 컷 편집·검증·자동 저장.
- **독립 테스트:** 실제 샘플 영상과 Fixture로 각각 테스트, 무음·지원 불가 영상 처리.
- **전체 테스트:** 구현 완료 후 등록, 타 모듈은 Stub으로 둔 채 검증.

## Application 담당 — **별도 서버 없이 Python 서비스 계층을 구현**

- **수정 위치:** [`application/service.py`](../src/application/service.py), [`application/storage.py`](../src/application/storage.py), [`application/plans.py`](../src/application/plans.py), [`application/jobs.py`](../src/application/jobs.py), [`bootstrap.py`](../src/bootstrap.py).
- **Input:** UI 호출, 공통 모델, 각 담당 모듈의 결과.
- **Output:** 프로젝트 조회·처리 결과·승인된 계획·작업 상태 및 렌더링 결과.
- **할 일:** 모듈 실행 순서, 결과 관계 검증·저장·조회·계획 승인, 백그라운드 실행 상태.
- **독립 테스트:** 다른 모듈은 Stub으로 두고 Python 함수만 직접 호출해 정상/실패 흐름 검사.
- **전체 테스트:** 실제 구현을 부분적으로 선택해 `ApplicationService` 전체 단계 검증.

## 공통 PR 제출 전 체크

1. 내 공개 인터페이스와 정확한 Pydantic 반환 모델을 지켰는가?
2. 정상 결과·빈 결과·오류 조건을 독립 테스트했는가?
3. 실제 구현이 완료된 다음에만 `bootstrap.py`에 등록했는가?
4. 다른 모듈의 Stub과 섞어서 통합 테스트했는가?
5. 공통 계약 변경을 사전 협의하고 모든 관련 문서/테스트를 수정했는가?

자세한 순서: [개발·테스트 흐름](DEVELOPMENT_TESTING.md).
