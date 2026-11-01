# 팀장 — 공통 계약·PR·최종 통합 관리

[← 담당자 목록](../ROLE_IMPLEMENTATION_MANUAL.md) · [2단계 개발·테스트 원칙](../DEVELOPMENT_TEST_FLOW.md)

## 목표

**담당자가 독립적으로 기능을 완성하고 테스트할 수 있도록 [Input/Output 계약](../INPUT_OUTPUT_CONTRACT_V1.md)을 유지하고, 완료된 구현들이 함께 작동하는지 검토합니다.** 팀장은 5명 중 한 명입니다.

## 공통 관리 파일

| 파일 | 관리할 사항 |
|---|---|
| [`src/video_assistant/core/models.py`](../../src/video_assistant/core/models.py) | Pydantic 입력·출력 형식 ([모델별 필드 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-model-fields)) |
| [`src/video_assistant/core/interfaces.py`](../../src/video_assistant/core/interfaces.py) | 공개 메서드 시그니처 |
| [`src/video_assistant/core/errors.py`](../../src/video_assistant/core/errors.py) | [오류 계약](../INPUT_OUTPUT_CONTRACT_V1.md#io-errors) |
| [`src/video_assistant/core/workflow.py`](../../src/video_assistant/core/workflow.py) | [호출·검증·저장 흐름](../MODULE_INTEGRATION_GUIDE.md) |
| [`src/video_assistant/core/plan_service.py`](../../src/video_assistant/core/plan_service.py) | [계획 계약](../INPUT_OUTPUT_CONTRACT_V1.md#io-plan-service) |
| [`storage.py`](../../src/video_assistant/core/storage.py), [`jobs.py`](../../src/video_assistant/core/jobs.py), [`config.py`](../../src/video_assistant/core/config.py) | 저장/작업/환경 설정 |
| [`src/video_assistant/bootstrap.py`](../../src/video_assistant/bootstrap.py) | 구현체 레지스트리의 구조·최종 통합 검토 |

## 단계별 팀장 업무

**1단계 — 팀원이 독립 개발 중일 때**

1. 팀원에게 `bootstrap.py` 등록을 먼저 요구하지 않습니다.
2. Fixture·Stub·공통 인터페이스가 안정적으로 유지되도록 관리합니다.
3. 입력·출력 계약의 변경 요청이 있으면 영향을 받는 담당자와 합의합니다.
4. 필요한 변경은 모델·Stub·Fixture·계약 테스트·문서를 함께 수정합니다.

**2단계 — 팀원의 모듈이 완성되어 통합을 시작할 때**

1. 담당자가 자기 브랜치에서 `bootstrap.py`의 **자기 레지스트리만 등록**하고 혼합 Stub/Real 테스트를 진행합니다.
2. 팀장은 담당자의 단위·계약 테스트와 혼합 통합 테스트 결과를 검토합니다.
3. PR에서 공통 파일의 변경 범위, 팩토리 생성 인자, 의존성, API 키 관리, 다른 브랜치와의 충돌을 검토합니다.
4. `develop`에 병합하고 전체 자동 테스트 및 실제 Streamlit 흐름을 재검증합니다.

## 담당자의 구현체 등록 예시

현재 [bootstrap.py](../../src/video_assistant/bootstrap.py)는 `ANALYZERS`에 `stub`, `simple`을, `RECOMMENDERS`에 `stub`, `keyword`를 제공합니다. 실제 LLM 등은 아직 없습니다.

담당자가 `LLMSegmentRecommender`를 작성했다면 자기 브랜치에서 해당 클래스를 import하고 `RECOMMENDERS`에 `"llm"` 항목을 추가합니다. 생성자에 인자가 필요하면 인자 없는 팩토리를 사용합니다. **Stub 기본값을 제거하지 않습니다.**

## PR 검토 체크

- [ ] 직접 호출하는 독립 테스트가 통과한다.
- [ ] 반환값과 참조 ID·시간·버전이 공통 계약에 맞는다.
- [ ] 기능 완성 후 자기 백엔드를 선택한 전체 흐름 테스트가 통과한다.
- [ ] `bootstrap.py`의 다른 레지스트리가 변경되지 않았다.
- [ ] 필요한 환경변수·의존성과 비밀키 처리 방식을 설명했다.
- [ ] `develop` 통합 후 전체 회귀 테스트가 통과한다.

참고: [Input/Output 계약](../INPUT_OUTPUT_CONTRACT_V1.md) · [팀 개발·Git 규칙](../TEAM_DEVELOPMENT_MANUAL.md) · [모델 출력 JSON](../CONTRACT_SAMPLE_OUTPUTS.md)
