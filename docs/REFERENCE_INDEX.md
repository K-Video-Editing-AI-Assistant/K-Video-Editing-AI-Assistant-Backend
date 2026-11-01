# 상세 자료 찾기 — 필요할 때만 읽으세요

처음부터 모든 문서를 읽을 필요는 없습니다. [시작 가이드](START_HERE.md)와 [내 담당자 페이지](ROLE_IMPLEMENTATION_MANUAL.md)를 먼저 보고, 막힌 질문에 해당하는 문서만 확인하세요.

| 이런 질문이 있을 때 | 열어볼 문서 | 확인할 내용 |
|---|---|---|
| `$env:` 없이 `.env`로 백엔드를 고르려면? | [`.env` 설정 가이드](ENV_CONFIGURATION.md) | 복사·수정·실행, 설정 우선순위, API 키 관리 |
| 반환형이 무엇이지? 필수 필드는? | [Input/Output 계약 명세서](INPUT_OUTPUT_CONTRACT_V1.md) | 시그니처·필드·빈 결과·ID/시간 규칙 |
| 출력 객체의 실제 JSON은? | [결과 JSON 예시](CONTRACT_SAMPLE_OUTPUTS.md) | VideoAsset, Transcript, VideoAnalysis, RecommendationResult, EditPlan, RenderResult |
| 내 `return`이 화면까지 어떻게 가지? | [모듈 연결 가이드](MODULE_INTEGRATION_GUIDE.md) | `Workflow` → 검증 → 저장 → UI 조회 |
| 기존 스켈레톤 구조는? | [아키텍처](ARCHITECTURE.md) | 처리 흐름·작업 관리·데이터 저장 |
| 언제 독립 테스트하고, 언제 등록·전체 흐름 테스트하나? | [2단계 개발·테스트](DEVELOPMENT_TEST_FLOW.md) | Fixture 직접 호출 → 모듈 완성 후 혼합 Stub/Real 검증 |
| 내 구현 알고리즘/테스트의 상세 설명은? | [상세 개발 매뉴얼](ROLE_IMPLEMENTATION_DETAILS.md) | 다섯 역할의 입력/출력 예시와 테스트 |
| 파일 수정·PR 규칙은? | [팀 개발 기본 매뉴얼](TEAM_DEVELOPMENT_MANUAL.md) | 공통 계약 변경·병합 정책 |
| 업무 분담표가 필요한가? | [팀원 업무 참고표](TEAM_TASKS.md) | 업무 분장 관점의 세부 체크 |
| 직접 추천 연결을 실습하고 싶은가? | [추천 실습](../RECOMMENDATION_WALKTHROUGH.md) | Stub → 키워드 추천 전환 |
| 모듈 결합을 눈으로 확인하고 싶은가? | `python scripts/show_contract_chain.py` | 실제 데이터·참조 ID 출력 |

**소스 코드의 최종 계약 정본:** [`core/models.py`](../src/video_assistant/core/models.py), [`core/interfaces.py`](../src/video_assistant/core/interfaces.py).

**공통 테스트 입력:** [`tests/fixtures/contract_samples.py`](../tests/fixtures/contract_samples.py). 외부 AI가 없어도 선행 결과를 제공받을 수 있습니다.

> 상세 문서는 초안/참고자료를 포함합니다. 문서와 코드가 다르면 **현재 소스의 공개 인터페이스와 모델을 먼저 확인한 뒤 팀장에게 계약 정합성 검토**를 요청하세요.
