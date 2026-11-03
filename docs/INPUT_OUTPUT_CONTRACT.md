# 모듈 Input/Output 계약

공통 모델의 정확한 필드·검증 규칙은 [`core/models.py`](../src/core/models.py), 구현할 공개 메서드는 [`core/interfaces.py`](../src/core/interfaces.py)에 있습니다. 이 문서는 **누가 데이터를 만들고, 누가 사용하는지**를 설명합니다.

| 순서 | 수행 주체 | Input | Output | 결과 소비자 |
|---|---|---|---|---|
| 1 | 영상처리 | MP4 bytes, 프로젝트 ID | `VideoAsset` | Application 저장소, Whisper, FFmpeg |
| 2 | 영상처리 | `VideoAsset` | `Transcript` | AI 전처리, AI 추천, SRT 저장 |
| 3 | AI | `Transcript` | `ProcessedTranscript` | AI 영상 분석 |
| 4 | AI | `ProcessedTranscript` | `VideoAnalysis` | 프로젝트 분석, AI 구간 추천 |
| 5 | AI | `Project`, `VideoAnalysis` 목록 | `ProjectAnalysis` | UI 키워드·AI 추천 |
| 6 | AI | `SearchRequest`, 자막·분석·프로젝트 분석 | `RecommendationResult` | 편집 계획 생성·UI |
| 7 | Application 담당 | 추천 결과, 사용자 선택·수정 | `EditPlan` / `ApprovedEditPlan` | UI·영상 편집 |
| 8 | 영상처리 | 영상 목록, 자막 목록, 승인 계획, 경로 | `RenderResult` | UI 다운로드 |

## 모든 담당자가 지킬 규칙

- Python 모듈은 **Pydantic 객체를 반환**하며, JSON 파일 저장은 Application 저장소가 담당합니다.
- 시간은 정수 `ms`, `[start_ms, end_ms)` 범위, `start_ms < end_ms`입니다.
- 추천·계획의 클립은 반드시 **원본 `video_id`**를 포함합니다.
- 원본 발언 근거는 `source_segment_ids`로 추적합니다.
- `RecommendationResult.clips`의 순서는 추천 순서, `EditPlan.clips`의 순서는 실제 렌더링 순서입니다.
- 결과가 없는 경우: `Transcript.segments=()`, `RecommendationResult.clips=()` 등의 **정상 빈 결과**.
- 파이프라인 실패: 공통 `AppError`나 실패 원인을 발생시키며, 내부 작업자가 `JobStatus.FAILED`로 기록합니다.
- 단순 Pydantic 필드 검증을 통과해도, **영상 ID·시간·원본 자막 참조 일치**를 Application 계층에서 검증합니다.

## 실제 코드로 확인

```powershell
python scripts/show_contract_chain.py
python -m pytest -v tests/test_module_contracts.py
```

`tests/fixtures/contract_samples.py`에 두 영상의 동일한 고정 입력이 들어 있습니다. **다른 담당자의 실제 AI/Whisper 구현은 테스트에 필요하지 않습니다.**

## 승인 경계

- 추천이 반환되면 ApplicationService가 `PlanClip`을 생성합니다.
- 사용자가 계획을 바꾸면 `version`이 증가합니다.
- 승인은 같은 버전의 DRAFT 상태에서만 허용하며, 승인 후 변경하려면 새 계획을 생성해야 합니다.
- 영상 편집기는 `ApprovedEditPlan`만 받습니다.
