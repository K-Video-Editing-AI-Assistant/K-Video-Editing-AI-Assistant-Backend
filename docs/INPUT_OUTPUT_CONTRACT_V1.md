# AI 영상편집 어시스턴트 — 모듈별 Input/Output 계약 명세서 v1.0

> **문서 길잡이:** 처음 보는 분은 [시작 가이드](START_HERE.md) → [내 담당 작업](ROLE_IMPLEMENTATION_MANUAL.md)을 먼저 읽으세요. 이 문서는 **필요한 세부 사항을 확인할 때** 사용하는 참고자료입니다.


> **상태:** 팀 검토·확정을 위한 기준안. 이 프로젝트 파일에 적용된 현행 계약을 기술한다. 팀 전원의 동의 여부까지 자동으로 확정된 것은 아니다.  
> **적용 코드:** `src/video_assistant/core/models.py`, `interfaces.py`, `workflow.py`, `plan_service.py`  
> **기술:** 단일 Python 앱, Pydantic v2, Streamlit, FFprobe/FFmpeg, 내부 Worker.  
> **목표:** 입력·출력·검증 규칙을 고정하여 다른 담당자의 실제 구현 없이도 개발·테스트·통합 가능하게 한다.

## 0. 가장 먼저 합의할 여섯 가지

1. **메서드가 반환하는 값은 JSON/`dict`/문자열이 아니라 `core/models.py`에 선언된 Pydantic 객체**다. 저장소에서 `model_dump_json()`으로 직렬화한다.
2. **출력은 다음 모듈이 소비하는 최소 정보 + 참조 무결성 정보**를 제공한다. 예: 클립 시작/종료와 추천 근거, 그리고 실제 자막 ID.
3. **영상 시간은 `int` 밀리초**다. 시간 범위는 `[start_ms, end_ms)`이며 `0 <= start_ms < end_ms <= video.duration_ms`다.
4. **입력에서 받은 식별자(ID)를 재생성하지 않는다.** 새 결과 객체의 `id`만 새로 만들고, `video_id`·`transcript_id` 등은 입력에서 받은 값을 그대로 전달한다.
5. **빈 결과와 실패는 다르다.** 무음 자막 `segments=()`, 무추천 `clips=()`는 정상이다. 모듈 실행 오류는 공통 오류로 보고하고, Worker가 실패 상태를 기록한다.
6. **각 실제 구현은 비어 있지 않은 `VERSION`을 선언**한다. 계약 자체 변경은 `core/` 수정과 함께 관련 Stub·Fixture·테스트·문서가 같이 바뀌어야 한다.

<a id="io-flow"></a>

## 1. 최종 사용자 흐름과 데이터 인계 지점

```text
UI: ingest(name, stream)                  -> VideoAsset
UI: submit_prepare(video.id)              -> JobStatus (작업 접수)
  Worker: Transcriber.transcribe(video)   -> Transcript
  Worker: ContentAnalyzer.analyze(text)   -> VideoAnalysis
  Worker: 두 결과를 검증·저장
UI: get_transcript/get_analysis           -> 저장된 객체 조회
UI: submit_recommend(SearchRequest)       -> JobStatus (작업 접수)
  Worker: recommender.recommend(request, transcript, analysis)
                                          -> RecommendationResult
  Worker: 결과 검증·저장, JobStatus.result_ref = RecommendationResult.id
UI: get_job(job.id)                       -> JobStatus
UI: get_recommendation(result_ref)        -> RecommendationResult
UI: create_plan(recommendation.id)        -> EditPlan(DRAFT)
UI: revise_plan(...) / approve_plan(...)  -> EditPlan / ApprovedEditPlan
UI: submit_render(plan.id, version)       -> JobStatus (작업 접수)
  Worker: VideoEditor.render(video, approved_plan, output_path)
                                          -> RenderResult
  Worker: 출력 파일·식별자·FFprobe 검증·저장, JobStatus.result_ref = RenderResult.id
UI: get_render_result(result_ref)         -> RenderResult (영상 재생/다운로드)
```

**유의:** `JobStatus`는 작업 접수·진행 상태다. 기능 담당자가 `JobStatus`를 반환하는 게 아니라 `transcribe`, `analyze`, `recommend`, `render`가 각각 자기 결과 객체를 반환한다. UI는 비동기 `submit_*`가 반환한 작업 ID로 상태를 폴링한다.

<a id="io-model-fields"></a>

## 2. 공통 모델의 정확한 필드·자료형

아래 `필수`는 생성할 때 직접 넣어야 하는 필드다. 나머지는 기본값을 쓸 수 있다. **최종 정본은 `core/models.py`.** 문자열 ID는 비어 있지 않아야 하며 파일 저장 시 안전한 영숫자·`_`·`-` 패턴을 사용한다(권장 `uuid4().hex`).

| 모델 | 직접 제공하는 필수 필드 | 기본값/자동 필드 | 관계·검증 |
|---|---|---|---|
| `VideoAsset` | `id: str`, `project_id: str`, `source_path: Path`, `original_name: str`, `duration_ms: int`, `sha256: str`, `has_audio: bool` | `created_at: AwareDatetime` | 업로드 계층 생성, MP4 탐지/길이 확인. `duration_ms > 0`, sha256=64자리 소문자 16진수 |
| `TranscriptSegment` | `id: str`, `start_ms: int`, `end_ms: int`, `text: str` | 없음 | `text` 비어 있지 않음, `start_ms < end_ms` |
| `Transcript` | `id: str`, `video_id: str`, `language: str`, `segments: tuple[TranscriptSegment,...]`, `transcriber_version: str` | `is_stub=False`, `created_at` | 자막 ID 중복/시간 역전/중첩 금지, 길이 초과는 Workflow 검사 |
| <a id="model-topicsection"></a>`TopicSection` | `id: str`, `title: str`, `start_ms: int`, `end_ms: int`, `segment_ids: tuple[str,...]` | 없음 | `segment_ids`는 1개 이상이며 중복 없음, Workflow에서 실제 자막 참조·영상 길이 확인 |
| `VideoAnalysis` | `id`, `video_id`, `transcript_id`, `summary: str`, `topics: tuple[TopicSection,...]`, `analyzer_version: str` | `is_stub=False`, `created_at` | 입력 `transcript.id` 연결, 자막 없으면 `summary=""`, `topics=()` 허용 |
| `SearchRequest` | `id: str`, `video_id: str`, `query: str` | `max_clips=5`, `created_at` | 검색어 비어 있으면 안 됨, `1 <= max_clips <= 20` |
| <a id="model-clipselection"></a>`ClipSelection` | `id: str`, `start_ms: int`, `end_ms: int` | `reason=""`, `source_segment_ids=()` | 순서: `clips` 튜플 순서. 수정된 클립은 자막 참조가 빈 경우도 모델상 허용됨 |
| `RecommendationResult` | `id`, `request_id`, `video_id`, `transcript_id`, `analysis_id`, `clips: tuple[ClipSelection,...]`, `recommender_version: str` | `is_stub=False`, `created_at` | 클립 ID 중복 금지, Workflow에서 영상·요청·버전·시간·참조·최대 개수 확인 |
| `EditPlan` | `id`, `video_id`, `request_id`, `recommendation_id`, `version: int`, `clips: tuple[ClipSelection,...]` | `status=DRAFT`, `created_at`, `approved_at=None` | 버전 1 이상, 클립 중복 ID 금지, 승인 시 비어 있으면 안 됨 |
| `ApprovedEditPlan` | `EditPlan`의 필수 필드 + `approved_at` | `status=APPROVED` | 승인 상태를 자료형으로 강제, 승인된 계획만 `render` 입력으로 허용 |
| `RenderResult` | `id`, `video_id`, `plan_id`, `plan_version: int`, `output_path: Path`, `duration_ms: int`, `renderer_version: str` | `is_stub=False`, `created_at` | FFprobe로 확인 가능한 출력 경로·길이. Workflow에서 출력 경로 및 계획 참조 검증 |
| <a id="model-jobstatus"></a>`JobStatus` | `id`, `kind: JobKind`, `project_id`, `video_id` | `state=QUEUED`, `stage`, `progress`, `result_ref`, 오류·시각 필드 | 성공: 결과 ID + `progress=100` + 완료 시각 필수. 실패: 오류 코드/메시지 + 완료 시각 필수 |

추가 규칙: 튜플로 표시한 요소들은 정해진 Pydantic 모델 객체로 구성한다. 생성 시 `str` → `int` 같은 암묵적 숫자 변환은 시간/버전/진행률 정수 필드에서 금지한다. `ContractModel`은 선언되지 않은 추가 필드를 금지하고 객체를 불변으로 둔다.

<a id="io-transcriber"></a>

## 3. 담당 ② 음성 인식 계약: `Transcriber`

| 항목 | 내용 |
|---|---|
| 개발 파일 | `src/video_assistant/transcription/whisper.py` |
| 기존 Stub | `transcription/stub.py`의 `StubTranscriber` |
| 공개 함수 | `transcribe(self, video: VideoAsset) -> Transcript` |
| 선행 조건 | `ApplicationService.ingest()`가 MP4를 저장하고 `VideoAsset`을 생성해 줌 |
| 담당 내부 작업 | 영상의 오디오 추출, 음성 인식, 문장/시간 분할, ms 변환, 빈 음성 처리, SRT 변환 보조 함수(필요 시) |
| 필수 반환 | `Transcript(id, video_id=video.id, language, segments, transcriber_version=self.VERSION, is_stub=False)` |
| 다음 소비자 | `ContentAnalyzer.analyze(transcript)`, 이후 `SegmentRecommender.recommend(..., transcript, ...)`, 자막 UI |
| 실행 시 검증 | Pydantic: 자막 순서/중첩/길이 조건. Workflow: 영상 ID/버전 일치, 영상 길이 이내 |
| 정상 빈 결과 | 무음이면 `segments=()`, `language="und"` 권장 |
| 실패 | 파일·디코딩·모델 실행 오류는 `TRANSCRIPTION_FAILED` 단계로 기록. 실패를 빈 자막으로 속이지 않음 |
| 완료 테스트 | 정상·무음·긴 자막·중복 ID·범위 초과·캐시 재사용 |

**독립 개발 Input:** `tests/fixtures/contract_samples.py::sample_video()`를 전달하면 Whisper 작업 전에도 입력 모델 구조를 확인할 수 있다. 음성 인식 실제 품질 평가는 실제 음성 영상으로 별도 수행한다. `StubTranscriber`는 실제 음성을 인식하지 않는다.

<a id="io-analyzer"></a>

## 4. 담당 ③ 내용 분석 계약: `ContentAnalyzer`

| 항목 | 내용 |
|---|---|
| 개발 파일 | `src/video_assistant/analysis/llm.py` |
| 선행 Input | `Transcript`; 음성 인식 구현이 없어도 `sample_transcript()` 사용 |
| 공개 함수 | `analyze(self, transcript: Transcript) -> VideoAnalysis` |
| 담당 내부 작업 | 전체 요약, 주제/소주제 추출, 유효한 원본 자막 ID 연결, 긴 자막 처리, 모델 응답 파싱 |
| 필수 반환 | `VideoAnalysis(id, video_id=transcript.video_id, transcript_id=transcript.id, summary, topics, analyzer_version=self.VERSION, is_stub=False)` |
| 다음 소비자 | `SegmentRecommender.recommend(..., analysis)`, UI의 전체 요약 표시 |
| 실행 시 검증 | Pydantic: 각 Topic 범위 및 참조 ID 목록의 중복 여부. Workflow: 자막/영상/버전 일치, 주제의 시간 범위 및 참조 ID 존재 여부 |
| 정상 빈 결과 | `Transcript.segments=()`이면 `topics=()` + 빈 요약 허용 |
| 실패 | LLM API·파싱 실패는 `ANALYSIS_FAILED`; 존재하지 않는 자막 ID 생성 금지 |
| 완료 테스트 | 정상·빈 자막·다중 주제·잘못된 자막 ID·LLM 오류·캐시 버전 변경 |

**독립 개발 Input:** `sample_transcript()`만 사용해 `LLMContentAnalyzer.analyze(...)`를 호출할 수 있다. 출력을 `VideoAnalysis`로 검증하면 음성 인식 담당자의 완성을 기다릴 필요 없다. 기존 연결 Stub은 `analysis/stub.py`이고 학습용 규칙 분석은 `analysis/simple.py`다.

<a id="io-recommender"></a>

## 5. 담당 ④ 자연어 검색·추천 계약: `SegmentRecommender`

| 항목 | 내용 |
|---|---|
| 개발 파일 | `src/video_assistant/recommendation/llm.py` |
| 선행 Input | `SearchRequest`, `Transcript`, `VideoAnalysis`. 실구현이 없으면 `sample_request()`, `sample_transcript()`, `sample_analysis()` 사용 |
| 공개 함수 | `recommend(self, request: SearchRequest, transcript: Transcript, analysis: VideoAnalysis) -> RecommendationResult` |
| 담당 내부 작업 | 의도 해석, 후보 검색, 관련성 판단, 클립 구간 및 배열 순서 결정, 중복 제거, 이유 생성 |
| 필수 반환 | `RecommendationResult(id, request_id=request.id, video_id=request.video_id, transcript_id=transcript.id, analysis_id=analysis.id, clips, recommender_version=self.VERSION, is_stub=False)` |
| 다음 소비자 | `PlanService.create_draft(recommendation_id)`가 `clips`로 `EditPlan` 생성, UI는 구간과 이유 표시 |
| 실행 시 검증 | Pydantic: 클립 시간·ID 중복. Workflow: 네 참조와 버전 일치, 개수 `<= max_clips`, 영상 길이와 원본 자막 참조 확인 |
| 정상 빈 결과 | 관련 장면이 없다면 `clips=()` — 작업 성공. 빈 계획은 만들 수 있지만 승인할 수 없음 |
| 실패 | LLM 실패/파싱 불능/잘못된 참조는 `RECOMMENDATION_FAILED`, 없는 구간을 임의 생성하면 안 됨 |
| 완료 테스트 | 정상 추천·무추천·상한 개수·비정상 참조·범위 초과·추천 순서·실제 품질 |

**순서 규칙:** `result.clips[0]`이 첫 번째 출력 클립이다. `source_segment_ids`는 모델상 빈 튜플도 허용되나, **AI가 자막 기반으로 추천한 경우는 근거 자막 ID를 넣는 것을 팀 기준으로 권장한다.** 사용자가 수동 추가·수정한 클립의 경우 근거 자막 ID가 없을 수 있다.

**LLM 연결 권장:** LLM에는 자막 ID/내용만 제공하고 선택한 자막 ID와 설명을 출력하게 한다. 시간을 임의 생성하지 말고 선택된 원본 `TranscriptSegment`의 `start_ms/end_ms`에서 계산한다.

**독립 개발:** `sample_transcript()` + `sample_analysis()`를 사용하여 실제 분석/Whisper 없이 개발하고 `tests/contract/test_module_io_contracts.py`를 참고한다. 현재 `keyword.py`는 LLM 없이 작동하는 실습용 구현이다.

<a id="io-plan-service"></a>

## 6. 공통 편집 계획 계약: `PlanService` (팀장 주도)

| 동작 | 입력 → 출력 | 규칙 |
|---|---|---|
| `create_draft(recommendation_id)` | 추천 ID → `EditPlan` | 저장소에서 추천을 조회, 클립 복사, `version=1`, `status=DRAFT` |
| `revise(plan_id, expected_version, clips)` | 초안 ID + 현재 버전 + 새 클립 튜플 → `EditPlan` | 초안만 수정, 저장 시 새 버전 생성, 시간·참조 검증 |
| `approve(plan_id, expected_version)` | 최신 초안 ID + 버전 → `ApprovedEditPlan` | 빈 클립 승인 불가. 승인 시 계획 내용 버전은 유지하고 상태만 전환 |
| `get_plan(plan_id, version=None)` | 계획 ID·선택 버전 → `EditPlan` | 버전별 조회 |

**특히 중요:** `RecommendationResult`는 편집 실행 명령이 아니다. `PlanService`가 생성·수정·승인한 `ApprovedEditPlan`만 편집기에 전달된다. 이전 계획 버전이나 승인 전 계획은 실행 불가. User UI에서 직접 계획 상태를 변경하지 않는다.

<a id="io-editor"></a>

## 7. 담당 ⑤ 영상 편집 계약: `VideoEditor`

| 항목 | 내용 |
|---|---|
| 개발 파일 | `src/video_assistant/editing/ffmpeg.py` |
| 선행 Input | `VideoAsset`, `ApprovedEditPlan`, `output_path: Path` |
| 공개 함수 | `render(self, video: VideoAsset, plan: ApprovedEditPlan, output_path: Path) -> RenderResult` |
| 담당 내부 작업 | 각 구간 절단·병합, 오디오 유무에 따른 처리, MP4/H.264(+AAC) 출력, FFprobe 검사, 임시 파일 정리 |
| 필수 반환 | `RenderResult(id, video_id=video.id, plan_id=plan.id, plan_version=plan.version, output_path=output_path, duration_ms=실제 측정 길이, renderer_version=self.VERSION, is_stub=False)` |
| 다음 소비자 | Workflow가 출력 참조와 파일을 검증·저장 → UI가 재생/다운로드 |
| 실행 시 검증 | 계획 ID·버전/파일 경로 일치, 출력 파일 FFprobe 가능, 기록 길이와 실제 길이 차이 100ms 이하(현재 코드 기준) |
| 정상 빈 결과 | 없음. 클립 없는 계획은 승인될 수 없으므로 `render()`까지 도달하지 않음 |
| 실패 | FFmpeg 실행/인코딩/출력 검증 실패는 `RENDER_FAILED` 또는 `OUTPUT_INVALID` |
| 완료 테스트 | 실제 컷 순서, 오디오 유무, 출력 MP4 유효성, 시간 오차, 중복/겹치는 클립, 실패 시 정리 |

**독립 개발 Input:** `sample_video()` + `sample_approved_plan()`을 바로 `render()`에 전달할 수 있다. `sample_video()`는 예제 MP4를 가리킨다. **`StubVideoEditor`는 승인 구간을 잘라내지 않고 원본을 복사하므로 컷 품질 검증에는 사용할 수 없다.**

<a id="io-ui"></a>

## 8. 담당 ① UI 계약: `ApplicationService` 소비자

UI는 독립 `Transcript`/`RecommendationResult` 생산자가 아니다. 버튼·폼 입력을 공통 서비스 호출로 변환하고, 그 서비스 결과를 표시한다.

| 사용자의 동작 | UI가 호출할 메서드 | 반환/화면에서 읽는 데이터 |
|---|---|---|
| 영상 등록 | `ingest(file_name, binary_stream)` | `VideoAsset` 및 `video.id` |
| 준비 시작 | `submit_prepare(video_id)` | `JobStatus.id` 저장 후 `get_job(id)` 폴링 |
| 자막·분석 조회 | `get_transcript(video_id)` / `get_analysis(video_id)` | `Transcript | None` / `VideoAnalysis | None` |
| 자연어 검색 | `submit_recommend(SearchRequest)` | `JobStatus`, 성공 후 `get_recommendation(result_ref)` |
| 계획 생성 | `create_plan(recommendation_id)` | `EditPlan`, 생성된 ID 보관 |
| 계획 수정 | `revise_plan(plan_id, expected_version, clips)` | 새 버전 `EditPlan` |
| 계획 승인 | `approve_plan(plan_id, expected_version)` | `ApprovedEditPlan` |
| 영상 생성 | `submit_render(plan_id, expected_version)` | `JobStatus`, 성공 후 `get_render_result(result_ref)` |
| 결과 재생/다운로드 | `get_render_result(result_id)` | `RenderResult.output_path` |

**주의:** 작업이 끝나기 전에 결과를 조회하지 않는다. UI는 `QUEUED/RUNNING/SUCCEEDED/FAILED`를 구별해 사용자에게 표시한다. 승인 검사·시간 범위 검사·FFmpeg 호출을 UI에 새로 구현하지 않는다. 구현 혼합 시 UI 상단에 하드코딩된 '전부 더미' 안내는 개선 필요(현재 데모 한계).

<a id="io-errors"></a>

## 9. 예외·실패·테스트 합격 규칙

| 구분 | 반드시 지켜야 할 동작 |
|---|---|
| 모델 자료형 오류 | Pydantic 모델 생성 실패/타입 불일치 → 정상 결과처럼 반환하지 않음 |
| 연관 ID 오류 | Workflow 검사 실패 → 해당 작업 실패로 기록, 결과를 저장하지 않음 |
| 영상 시간 오류 | `0 <= start < end <= video.duration_ms` 위반 → 실패 |
| 무음 | `Transcript.segments=()` 정상, 분석 `topics=()` 가능 |
| 무추천 | `RecommendationResult.clips=()` 정상, 사용자에게 추천 없음 표시 |
| 승인 전/구간 없음 | 렌더링 금지 또는 승인 실패 |
| FFmpeg 실패 | `RenderResult` 성공 반환 금지, 임시 파일 정리 |
| 작업 상태 | 실패면 `JobStatus.state=FAILED`, `error_code/error_message` 저장 |
| 캐시 | 기존 준비 결과는 `transcriber_version`/`analyzer_version`이 같은 경우 재사용됨 |

**현행 코드 보장 범위:** Pydantic과 Workflow는 타입, 버전, 참조 존재, 기본 시간 등을 검사한다. **내용의 적절성**(추천이 실제 요청과 관련 있는가, 주제가 정확한가, 렌더 결과가 요청한 정확한 장면을 담는가)은 별도의 품질·통합 테스트가 필요하다. 예를 들어 주제의 `segment_ids`는 존재 여부를 확인하지만, 주제 시작·끝이 참조 자막을 완전히 덮는지는 현재 추가 검증하지 않는다. 이 항목은 계약 강화를 위한 팀 검토 대상으로 남긴다.

<a id="io-fixtures"></a>

## 10. 준비된 Fixture와 Stub을 활용하는 방법

### 10.1 공통 고정 Fixture

```python
from tests.fixtures.contract_samples import (
    sample_video, sample_transcript, sample_analysis,
    sample_request, sample_recommendation, sample_approved_plan,
)

video = sample_video()
transcript = sample_transcript(video)
analysis = sample_analysis(transcript)
request = sample_request(video)
# 실제 추천 모듈 구현 중이면:
result = my_recommender.recommend(request, transcript, analysis)
assert result.video_id == video.id
```

Fixture의 ID와 시간은 항상 같다(`s1: 0~2000`, `s2: 2000~5000`, `s3: 5000~8000`). 따라서 선행 구현 없이 내 모듈을 단독 호출할 수 있다. 경로는 반드시 **프로젝트 루트에서 테스트 명령으로 실행**한다.

### 10.2 이미 연결된 Stub

| 선행 모듈 미완성 | 사용할 구현 | 대체 데이터 |
|---|---|---|
| 음성 인식 | `StubTranscriber` | 데모 영상 길이에 맞는 가짜 자막(무음 입력이면 빈 자막) |
| 내용 분석 | `StubContentAnalyzer` | 전달받은 자막 구간에서 가짜 주제·요약 |
| 구간 추천 | `StubSegmentRecommender` | 앞쪽 자막 기준 가짜 추천, `추천 없음`이면 빈 결과 |
| 편집 | `StubVideoEditor` | 출력 경로에 **원본 영상 복사**, 클립 잘라내지 않음 |

`bootstrap.py`의 레지스트리에 네 Stub이 등록되어 있고, 기본 설정은 모두 `stub`이다. `ANALYZER_BACKEND=simple`과 `RECOMMENDER_BACKEND=keyword`는 실습용 작은 실제 구현을 선택한다. `whisper`/`llm`/`ffmpeg`는 팀원이 구현·등록하기 전에는 선택할 수 없다.

### 10.3 실제 실행과 테스트

```bash
python -m pip install -e ".[test]"
python -m pytest -q tests/contract/test_module_io_contracts.py
python -m pytest -q tests/integration/test_contract_stub_matrix.py
python -m pytest -q
python scripts/show_contract_chain.py
python scripts/smoke_test.py
```

MP4 검증에는 `ffprobe`가 PATH에 있어야 한다. 마지막 세 명령은 공통 모델뿐 아니라 실제 업로드와 Stub 편집기까지 검사한다. 자체 모듈을 추가했을 때는 `tests/contract/test_module_io_contracts.py`를 복사하여 구현 클래스로 변경해 검증한다.

<a id="io-registration"></a>

## 11. 담당자 등록 및 팀장 계약 변경 관리

1. 변경 필요성 접수: 요청한 모듈과 다음 소비자의 요구를 명시한다.
2. 팀장 + 영향을 받는 담당자가 필드·타입·시간·빈 결과·실패 규칙에 합의한다.
3. `core/models.py`, `interfaces.py` 변경 시 네 Stub, 공통 Fixture, 계약·통합 테스트, 문서를 한 PR에서 동기화한다.
4. 각 담당자가 Fixture 기반 독립 테스트로 구현을 먼저 검증한다. 이 단계에는 `bootstrap.py` 등록이 필요 없다.
5. 구현이 준비되면 담당자가 **자기 브랜치에서** `bootstrap.py` 레지스트리에 **인자 없는 클래스/팩토리**를 등록한다. 새 구현체만 켜고 나머지는 Stub으로 테스트한다.
6. 담당자는 등록 코드와 독립·전체 흐름 테스트 결과를 함께 PR로 제출한다. 팀장은 계약·충돌을 검토하고 병합 후 `python -m pytest -q` 및 전체 UI 흐름을 확인한다.

등록 예: `RECOMMENDERS = {"stub": StubSegmentRecommender, "keyword": KeywordSegmentRecommender, "llm": build_llm_recommender}`. 생성자에서 키가 필요하면 `build_llm_recommender()`에서 안전하게 읽는다. `.env.example`을 `.env`로 복사하면 프로젝트가 자동으로 읽는다. 자세한 내용은 [환경 설정 가이드](ENV_CONFIGURATION.md)를 참고한다.

## 12. 아직 팀 합의가 필요한 품질/정책 선택 (계약 v1과 구분)

- 화자 분리(`speaker_id`)가 MVP 범위에 필요한지
- 같은 문장의 문맥 확장/연속 자막 결합·추천 길이 기준
- `TopicSection` 범위가 참조 자막 시간 전체를 포함하도록 강제할지
- 추천된 클립에 `source_segment_ids` 최소 1개를 강제할지(수동 편집은 예외)
- 실제 FFmpeg의 출력 시간 허용 오차와 오디오 동기화 품질 기준
- LLM 평가 지표(관련성, 정확도, 설명 적절성)와 승인 기준

**이 항목들은 현행 v1 계약을 조용히 바꾸지 말고 변경 PR에서 결정한다.**
