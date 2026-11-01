# 담당 5 — FFmpeg 편집: 내가 해야 할 일

[← 역할 목록](../ROLE_IMPLEMENTATION_MANUAL.md)

## 최종 목표

**승인된 구간을 실제 MP4 영상에서 추출·병합하고 검증된 [RenderResult](../CONTRACT_SAMPLE_OUTPUTS.md#renderresult)를 반환**한다.

| 항목 | 내용 |
|---|---|
| **받는 입력** | [VideoAsset](../CONTRACT_SAMPLE_OUTPUTS.md#videoasset), [ApprovedEditPlan](../CONTRACT_SAMPLE_OUTPUTS.md#approvededitplan), `output_path: Path` |
| **만들 결과** | 생성한 MP4 경로·실제 길이·승인 계획 ID/버전을 가진 [RenderResult](../CONTRACT_SAMPLE_OUTPUTS.md#renderresult) |
| **그다음 사용처** | [Workflow 연결 흐름](../MODULE_INTEGRATION_GUIDE.md)에서 결과 검증·저장 → [UI](ui.md)가 재생/다운로드 |
| **공개 함수** | [`VideoEditor.render(...)`](../../src/video_assistant/core/interfaces.py) ([입출력 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-editor)) |

## 수정할 곳

- 실제 구현: [`src/video_assistant/editing/ffmpeg.py`](../../src/video_assistant/editing/ffmpeg.py)
- 참고용: [`src/video_assistant/editing/stub.py`](../../src/video_assistant/editing/stub.py) (**원본을 복사할 뿐 실제 편집은 안 함**)
- 새 테스트: `tests/integration/test_ffmpeg_real.py` (직접 만들 파일, 아직 링크 없음)

## 1단계 — 내 기능 구현·독립 테스트

1. [`VideoEditor` 인터페이스](../../src/video_assistant/core/interfaces.py)와 [ApprovedEditPlan](../CONTRACT_SAMPLE_OUTPUTS.md#approvededitplan), [RenderResult](../CONTRACT_SAMPLE_OUTPUTS.md#renderresult)를 확인한다.
2. `FFmpegVideoEditor(VideoEditor)`와 `VERSION`을 작성한다.
3. `plan.clips` **배열 순서대로** `[start_ms, end_ms)` 구간을 추출해 연결한다.
4. 결과를 지정된 `output_path`에 MP4로 저장하고 FFprobe로 재생 가능 여부/실제 길이를 확인한다.
5. `video_id=video.id`, `plan_id=plan.id`, `plan_version=plan.version`, `is_stub=False`를 포함해 반환한다.
6. `sample_video()`, `sample_approved_plan()`으로 `render()`를 **직접 호출**해 실제 컷 편집·출력 검증을 먼저 수행한다. 이때 `bootstrap.py`는 필요 없다.

## 2단계 — 기능이 준비되면 전체 흐름 테스트

1. 실제 편집 기능이 완성되면 **자신의 브랜치에서** [`bootstrap.py`](../../src/video_assistant/bootstrap.py)의 `EDITORS`에 등록하고, 다른 모듈 Stub과 전체 흐름 테스트를 한다.
2. 독립/전체 흐름 검증 결과를 포함해 PR을 제출한다.

## 추천 모듈이 미완성이라면?

[`tests/fixtures/contract_samples.py`](../../tests/fixtures/contract_samples.py)의 `sample_video()` + `sample_approved_plan()`이 이미 연결 가능한 입력을 준다. 영상의 실제 컷이 올바른지 검증할 때는 직접 FFmpeg를 실행해야 한다.

**개발 순서:** 독립 테스트를 먼저 완료한 뒤 전체 흐름 테스트로 진행합니다. [단계별 테스트 상세](../DEVELOPMENT_TEST_FLOW.md)

## 완료 체크

- [ ] 승인된 계획 외에는 렌더링하지 않는다.
- [ ] 오디오 유무, 인코딩, 구간 순서, 출력 영상 길이를 검증한다.
- [ ] FFmpeg 인자는 명령 문자열이 아닌 배열로 만들고 `shell=False`로 실행한다.
- [ ] 실패 시 손상된 결과 파일을 성공으로 반환하지 않는다.
- [ ] 원본 복사 Stub 테스트와 **실제 컷 편집 테스트**를 구분한다.

**더 찾아보기:** [영상 편집 계약 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-editor) · [출력 JSON](../CONTRACT_SAMPLE_OUTPUTS.md#renderresult) · [아키텍처](../ARCHITECTURE.md).
