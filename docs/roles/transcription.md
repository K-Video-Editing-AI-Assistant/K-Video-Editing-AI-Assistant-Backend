# 담당 2 — 음성 인식: 내가 해야 할 일

[← 역할 목록](../ROLE_IMPLEMENTATION_MANUAL.md)

## 최종 목표

**영상의 음성을 읽어 정확한 자막·시간을 만들고 [Transcript](../CONTRACT_SAMPLE_OUTPUTS.md#transcript) 객체를 반환**한다.

| 항목 | 내용 |
|---|---|
| **받는 입력** | [VideoAsset](../CONTRACT_SAMPLE_OUTPUTS.md#videoasset) (원본 MP4 경로·영상 길이·오디오 유무·ID) |
| **만들 결과** | [Transcript](../CONTRACT_SAMPLE_OUTPUTS.md#transcript) (언어, 자막 ID/시간/문장, 버전; 자막 단위는 `TranscriptSegment`) |
| **그다음 사용처** | [내용 분석](analysis.md)의 `analyze()`, [검색·추천](recommendation.md)의 `recommend()`, UI 자막 표시 |
| **공개 함수** | [`Transcriber.transcribe(...)`](../../src/video_assistant/core/interfaces.py) ([입출력 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-transcriber)) |

## 수정할 곳

- 실제 구현: [`src/video_assistant/transcription/whisper.py`](../../src/video_assistant/transcription/whisper.py)
- 비교용 Stub: [`src/video_assistant/transcription/stub.py`](../../src/video_assistant/transcription/stub.py) **읽기만, 삭제·덮어쓰기 금지**
- 새 테스트: `tests/contract/test_whisper_contract.py` (직접 만들 파일, 아직 링크 없음)

## 1단계 — 내 기능 구현·독립 테스트

1. [`core/interfaces.py`](../../src/video_assistant/core/interfaces.py)에서 `Transcriber`, [`core/models.py`](../../src/video_assistant/core/models.py)에서 `Transcript` 구조를 확인한다. 실제 값은 [Transcript JSON 예시](../CONTRACT_SAMPLE_OUTPUTS.md#transcript) 참고.
2. `whisper.py`에 `WhisperTranscriber(Transcriber)`와 `VERSION`을 정의한다.
3. 영상에서 음성을 인식하고 각 자막에 **고유 ID·정수 밀리초 시작/종료·텍스트**를 채운다.
4. `video_id=video.id`, `transcriber_version=self.VERSION`, `is_stub=False`인 `Transcript` 객체를 반환한다.
5. `sample_video()`와 실제 발화 샘플로 `transcribe()`를 **직접 호출**하는 단위·계약 테스트를 반복한다. 이 단계에는 `bootstrap.py` 등록이 필요 없다.

## 2단계 — 기능이 준비되면 전체 흐름 테스트

1. 기능·테스트가 준비되면 **자신의 브랜치에서** [`bootstrap.py`](../../src/video_assistant/bootstrap.py)의 `TRANSCRIBERS`에 등록하고, 다른 모듈은 Stub으로 두어 전체 흐름을 검증한다.
2. 결과 및 등록 변경을 포함한 PR을 제출한다.

## 선행 기능이 없으면?

업로드·FFprobe 흐름을 따로 실행하지 않아도 [`tests/fixtures/contract_samples.py`](../../tests/fixtures/contract_samples.py)의 `sample_video()`로 [VideoAsset](../CONTRACT_SAMPLE_OUTPUTS.md#videoasset)을 얻는다. 실제 Whisper 호출을 테스트하려면 모델 의존성·실제 발화가 있는 샘플 영상도 별도로 준비해야 한다.

**개발 순서:** 독립 테스트를 먼저 완료한 뒤 전체 흐름 테스트로 진행합니다. [단계별 테스트 상세](../DEVELOPMENT_TEST_FLOW.md)

## 완료 체크

- [ ] 무음 영상은 `segments=()` 정상 결과다.
- [ ] `0 <= start_ms < end_ms <= video.duration_ms`이고 자막 구간은 시간순이다.
- [ ] 실패 시 정상 자막을 가장하지 않는다.
- [ ] 계약 테스트와 실제 발화 인식 테스트를 각각 확인한다.

**더 찾아보기:** [음성 인식 계약 규칙](../INPUT_OUTPUT_CONTRACT_V1.md#io-transcriber) · [Transcript JSON](../CONTRACT_SAMPLE_OUTPUTS.md#transcript) · [독립 테스트 방법](../DEVELOPMENT_TEST_FLOW.md).
