# 담당자별 개발 업무 매뉴얼 — 독립 테스트 먼저

[← 시작 가이드](START_HERE.md) · [독립/전체 테스트 방법](DEVELOPMENT_TEST_FLOW.md) · [입출력 계약](INPUT_OUTPUT_CONTRACT_V1.md)

## 모두에게 동일한 개발 순서

**1단계 — 구현 + 독립 테스트**

1. 내 역할 페이지에서 **입력, 출력, 공개 함수, 수정할 파일**을 확인합니다.
2. 자기 모듈에 실제 기능을 구현합니다. 기존 Stub은 유지합니다.
3. 선행 모듈이 완성되지 않았으면 공통 Fixture를 사용합니다.
4. 자기 공개 함수를 **직접 호출**해 올바른 Pydantic 결과가 나오는지 테스트합니다. 정상/빈 결과/실패와 실제 기능 품질을 확인합니다.

**2단계 — 모듈이 준비된 다음 전체 흐름 테스트**

5. 자신의 개발 브랜치에서 `bootstrap.py`의 **자기 모듈 등록 부분만** 수정합니다.
6. 내 구현만 실제로 선택하고 다른 미완성 기능은 Stub으로 유지하여 전체 흐름을 검증합니다.
7. 전체 테스트 실행 후 구현·등록·테스트를 포함해 PR을 제출합니다. 팀장·관련 담당자가 검토합니다.

> **등록은 독립 테스트의 선행 조건이 아닙니다.** 팀장에게 등록을 요청하느라 개발을 멈출 필요가 없습니다. 등록은 **완성 후 통합 검증 단계**의 작업입니다.

## 담당별 해야 할 일

| 담당 | 구현 파일 (`src/video_assistant/` 기준) | 구현할 기능 | Output/주요 계약 | 역할별 가이드 |
|---|---|---|---|---|
| **UI** | `ui/app.py`, `ui/components.py` | 업로드, 진행 상태, 검색/승인, 결과 화면 | [ApplicationService](../src/video_assistant/core/interfaces.py) 사용 | [UI](roles/ui.md) |
| **음성 인식** | `transcription/whisper.py` | 발화·시간 인식 | [Transcript](CONTRACT_SAMPLE_OUTPUTS.md#transcript) | [음성](roles/transcription.md) |
| **내용 분석** | `analysis/llm.py` | 요약·주제/자막 연결 | [VideoAnalysis](CONTRACT_SAMPLE_OUTPUTS.md#videoanalysis) | [분석](roles/analysis.md) |
| **검색·추천** | `recommendation/llm.py` | 자연어 관련 구간·순서·근거 | [RecommendationResult](CONTRACT_SAMPLE_OUTPUTS.md#recommendationresult) | [추천](roles/recommendation.md) |
| **영상 편집** | `editing/ffmpeg.py` | 승인 구간 추출·병합 및 검증 | [RenderResult](CONTRACT_SAMPLE_OUTPUTS.md#renderresult) + MP4 | [편집](roles/editing.md) |
| **팀장(5명 중 한 명)** | 공통 계약과 `bootstrap.py` | 계약 조율·PR 검토·병합 | 호환성 관리 | [팀장](roles/lead.md) |

## 작업 완료를 나누어 판단하기

- **독립 구현 완료:** 입력 Fixture로 직접 실행, 올바른 Output, 정상/빈 결과/실패 테스트, 실제 핵심 품질 확인.
- **통합 검증 완료:** 자기 브랜치에서 `bootstrap.py` 등록, 나머지 Stub과 연결, 전체 흐름·회귀 테스트 통과.
- **팀 공유 완료:** PR 리뷰와 `main` 병합 후 전체 흐름이 유지됨.

## 막힌 경우 찾아볼 문서

표에서 **모델명**을 클릭하면 실제 출력 JSON 예시로, **담당자**를 클릭하면 구현 순서가 있는 역할 페이지로 이동합니다. 필드 타입과 오류 규칙은 [입출력 계약의 모델 표](INPUT_OUTPUT_CONTRACT_V1.md#io-model-fields)에서 확인하세요.

- 내가 함수에 어떤 데이터를 넣고 어떤 필드를 반환하나? → [Input/Output 계약](INPUT_OUTPUT_CONTRACT_V1.md)
- Fixture로 어떻게 직접 테스트하나? → [개발·테스트 2단계](DEVELOPMENT_TEST_FLOW.md)
- `bootstrap.py` 등록과 환경변수는? → [모듈 연결 가이드](MODULE_INTEGRATION_GUIDE.md)
- 기존 자세한 설명은? → [담당자별 상세 가이드](ROLE_IMPLEMENTATION_DETAILS.md)
- 문서 전체 목차 → [상세 참고자료](REFERENCE_INDEX.md)
