# 처음 시작하는 팀원을 위한 시작 가이드

**이번에 기억할 순서: `내 기능 구현 → 독립 테스트 → 기능 완성 → 전체 흐름 테스트 → PR`**

독립 테스트가 끝나기 전에는 `bootstrap.py` 등록이나 다른 모듈과의 연결을 신경 쓰지 않아도 됩니다.

## 1. 처음 할 일

- [ ] [설치·실행](SETUP_AND_RUN.md)과 [`.env` 설정](ENV_CONFIGURATION.md)으로 개발 환경을 준비하고 기존 Stub 프로그램을 실행해 본다.
- [ ] [내 역할 페이지](ROLE_IMPLEMENTATION_MANUAL.md)를 선택하여 구현 파일, Input, Output을 확인한다.
- [ ] 선행 기능 대신 공통 Fixture를 사용하여 **내 함수만 직접 호출하는 테스트**를 작성한다.
- [ ] 실제 기능을 구현하고 정상·빈 결과·실패 테스트를 반복하여 통과시킨다.
- [ ] 내 모듈이 준비되면 **자신의 브랜치에서** `bootstrap.py`에 등록하고 다른 모듈의 Stub과 전체 흐름 테스트를 수행한다.
- [ ] 구현 파일·등록 코드·테스트 결과를 함께 PR로 제출한다.

## 2. 내 담당자 페이지 선택

| 담당 | 내 출력 또는 주요 계약 | 작업 안내 |
|---|---|---|
| UI | `ApplicationService` 호출과 결과 화면 | [UI 담당](roles/ui.md) |
| 음성 인식 | `VideoAsset` → `Transcript` | [음성 인식 담당](roles/transcription.md) |
| 내용 분석 | `Transcript` → `VideoAnalysis` | [내용 분석 담당](roles/analysis.md) |
| 검색·추천 | 요청 + 자막 + 분석 → `RecommendationResult` | [검색·추천 담당](roles/recommendation.md) |
| 영상 편집 | 승인된 계획 → 실제 MP4 + `RenderResult` | [영상 편집 담당](roles/editing.md) |
| 팀장 | 계약 변경·PR 검토·최종 통합 | [팀장](roles/lead.md) |

## 3. 두 단계의 차이

| | 1단계: 독립 테스트 | 2단계: 전체 흐름 테스트 |
|---|---|---|
| **언제?** | 기능 구현 도중부터 | 자기 모듈의 기능과 테스트가 준비된 후 |
| **Input** | `tests/fixtures/contract_samples.py`의 고정 데이터 | 다른 모듈 Stub + 실제 앱의 입력 |
| **실행 방법** | 자기 클래스의 공개 함수를 직접 호출 | `bootstrap.py`에 등록한 뒤 `ApplicationService`에서 실행 |
| **수정 파일** | 자기 모듈과 테스트 파일 | 자기 모듈 + 자기 레지스트리 항목 + 통합 테스트 |
| **확인할 것** | 내 알고리즘·반환 모델·오류 처리 | 저장·UI·후속 모듈까지 문제없이 연결되는지 |
| **팀장 참여** | 계약 변경이 필요할 때만 | PR 리뷰·main 통합 때 |

## 4. 내 함수가 다른 기능까지 전달되는 구조

```text
[Fixture] -> [내 구현의 공개 메서드] -> [Pydantic Output]
                ▲
          1단계에서 직접 테스트

[UI] -> [ApplicationService] -> [내 구현] -> [Workflow 검증·저장] -> [후속 기능/UI]
                                 ▲
                       2단계에서 Stub과 연동 테스트
```

기능 담당자는 **정해진 Pydantic 결과를 반환**하면 됩니다. UI 호출, 저장 및 승인 기능까지 자기 모듈에서 직접 작성하지 않습니다.

**다음에 볼 문서:** [2단계 개발·테스트 상세 가이드](DEVELOPMENT_TEST_FLOW.md) · [정확한 I/O 필드](INPUT_OUTPUT_CONTRACT_V1.md) · [필요할 때 보는 상세 자료](REFERENCE_INDEX.md)
