# 담당자별 작업 가이드 (PR 분배 기준)

> **문서 길잡이:** 처음 보는 분은 [시작 가이드](START_HERE.md) → [내 담당 작업](ROLE_IMPLEMENTATION_MANUAL.md)을 먼저 읽으세요. 이 문서는 **필요한 세부 사항을 확인할 때** 사용하는 참고자료입니다.


## 시작 전 공통 확인

- 설치: `python -m pip install -e ".[test]"`
- 실험: `python scripts/smoke_test.py`
- 테스트: `python -m pytest -q`
- 소스 트리: `src/video_assistant/`
- 공개 입력/출력: `core/models.py`, `core/interfaces.py`에서 확인
- 다른 기능의 구체 클래스를 직접 import하지 말고 `bootstrap.py`가 구현체를 주입하게 합니다.

| 담당 | 주 작업 경로 | 구현 목표 | 별도 테스트 |
|---|---|---|---|
| 1. UI | `ui/app.py`, `ui/components.py` | 업로드/진행률/자막·분석/추천/구간 수정/승인/출력 UX 개선 | `tests/unit/test_ui.py` 등 |
| 2. 음성 인식 | `transcription/whisper.py` | 오디오 추출, Whisper STT, 시간 정규화, 자막, 무음 처리 | `tests/contract/test_transcriber.py` |
| 3. 내용 분석 | `analysis/llm.py` | 전체 요약, topic/segment 연결, 긴 자막 처리, 모델 검증 | `tests/contract/test_analyzer.py` |
| 4. 검색·추천 | `recommendation/llm.py` | 사용자 요청 분석, 관련 발언 검색, 이유/순서 제안, 빈 결과 | `tests/contract/test_recommender.py` |
| 5. 영상 편집 | `editing/ffmpeg.py` | 승인 구간 추출/병합, MP4 인코딩, FFprobe 결과 검증 | `tests/integration/test_ffmpeg_render.py` |

각 모듈의 `stub.py`는 현재 공통 스켈레톤용 고정 응답입니다. 담당자는 Stub과 실제 구현을 분리하고, 필요한 내부 보조 파일은 자기 디렉터리에 추가할 수 있습니다.

## 담당 1 — UI

- `app.py`: `ApplicationService`만 호출, 백엔드 모듈을 직접 호출하지 않음.
- `components.py`: 자막, 검토, 승인, 작업 상태 컴포넌트 분리.
- UI 수정 시 계획 검증·승인 코드를 프론트에 복제하지 말 것.
- 업로드 파일·클립 미리보기·실패 상태·빈 추천을 각각 표시할 것.

## 담당 2 — 음성 인식

- 구현할 클래스 예: `WhisperTranscriber(Transcriber)`.
- 공개 메서드: `transcribe(self, video: VideoAsset) -> Transcript`.
- `VERSION` 문자열 필수. 자막 구간은 음이 없는 경우 `()` 허용.
- 반환한 `Transcript.video_id == video.id`, 구간은 `video.duration_ms` 안에 있어야 함.
- 자막을 파일로 별도 내보내려면 모듈 내부 도우미로 구현하고 저장 책임은 공통 담당과 조율.

## 담당 3 — 내용 분석

- 구현할 클래스 예: `LLMContentAnalyzer(ContentAnalyzer)`.
- 공개 메서드: `analyze(self, transcript: Transcript) -> VideoAnalysis`.
- `VERSION` 문자열 필수. 결과는 요청과 무관하게 재사용 가능한 내용 분석이어야 함.
- `VideoAnalysis.transcript_id == transcript.id`, topic이 참조하는 모든 `segment_ids` 존재.
- 모델 응답이 Pydantic 검증 실패하면 공통 오류로 전파.

## 담당 4 — 검색·추천

- 구현할 클래스 예: `LLMSegmentRecommender(SegmentRecommender)`.
- 공개 메서드: `recommend(self, request, transcript, analysis) -> RecommendationResult`.
- `VERSION` 문자열 필수. `clips` 수는 `request.max_clips` 이하.
- 추천 근거(`reason`)와 자막 참조(`source_segment_ids`)를 가능한 한 제공.
- 검색 결과가 없으면 실패 대신 `clips=()`.

## 담당 5 — 영상 편집

- 구현할 클래스 예: `FFmpegVideoEditor(VideoEditor)`.
- 공개 메서드: `render(self, video: VideoAsset, plan: ApprovedEditPlan, output_path: Path) -> RenderResult`.
- `VERSION` 문자열 필수. 플랜 순서로 구간 추출·병합.
- mp4 H.264 / AAC(오디오가 있으면) 인코딩, 실제 출력 MP4 및 FFprobe 검증.
- 원본/출력 파일 외부 쓰기 금지, FFmpeg 옵션은 신뢰 가능한 내부 코드에서 조합.

## 공통 파일 배정 (팀장이 직접 또는 별도 작업자로 분배)

| 파일 | 구현된 최소 역할 | 유지/보완 담당 |
|---|---|---|
| `core/models.py` | Pydantic 계약/모델 검증 | 팀장 주도 · 전체 합의 |
| `core/interfaces.py` | ABC 계약 | 팀장 주도 · 전체 합의 |
| `core/errors.py` | 오류 코드 | 팀장 주도 · 전체 합의 |
| `core/storage.py` | JSON 저장·CAS | 공통 담당 배정 필요 |
| `core/plan_service.py` | 편집 계획 검증·승인 | 공통 담당 배정 필요 |
| `core/jobs.py` | 장시간 작업/상태 저장 | 공통 담당 배정 필요 |
| `core/workflow.py` | 단계별 실행·교차 검증 | 공통 담당 배정 필요 |
| `core/config.py`, `bootstrap.py` | 설정·어댑터 연결 | 팀장 주도 |

## 담당자 구현 완료 기준

1. 공개 ABC의 구현 및 `VERSION` 제공.
2. 정상/빈 결과/잘못된 입력/모델 실패 테스트.
3. 실제 구현 파일이 타 모듈 구체 클래스에 의존하지 않음.
4. 자기 담당 파일을 수정한 PR 제출.
5. **독립 테스트로 기능을 먼저 완성한다.** 이후 담당자가 자기 브랜치에서 `bootstrap.py`에 어댑터를 등록한다.
6. 등록 후 기존 Stub들과 전체 흐름 테스트를 직접 수행하고 구현·등록·테스트 내역을 PR로 제출한다.

## Git 충돌이 없어도 통합 테스트가 필요한 이유

- 데이터 필드/시간 단위 불일치
- 모델·프롬프트 버전에 따른 캐시 재사용 오류
- 긴 작업 중 상태 및 오류 처리 미흡
- FFmpeg 예상 길이/출력 검증 불일치

PR은 최신 파일을 복사해 덮어쓰지 말고 Git의 정상 병합 절차로 반영하세요.
