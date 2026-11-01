# 모듈 개발·결과 데이터·전체 프로그램 연결 가이드

> **문서 길잡이:** 처음 보는 분은 [시작 가이드](START_HERE.md) → [내 담당 작업](ROLE_IMPLEMENTATION_MANUAL.md)을 먼저 읽으세요. 이 문서는 **필요한 세부 사항을 확인할 때** 사용하는 참고자료입니다.


> 적용 대상: 이 프로젝트의 실제 `src/video_assistant/` 소스 (2026-10, 스켈레톤 v1 기반)  
> 대상 독자: UI / Transcription / Analysis / Recommendation / Editing 담당자 및 팀장  
> 목적: **내가 어느 파일에서 무엇을 구현하고, 어떤 객체를 반환하며, 누가 그것을 받아 다음 단계로 넘기는지**를 확인한다.

## 0. 가장 중요한 세 문장

1. 기능 담당자는 **`core/interfaces.py`에 약속된 메서드**를 자신의 모듈에서 구현하고, `core/models.py`의 **Pydantic 모델 객체**를 반환한다.
2. 다른 담당자의 모듈을 **직접 호출하거나 결과 JSON을 손으로 넘기지 않는다.** 이미 작성된 `core/workflow.py`가 결과를 확인·저장하고 다음 단계에서 다시 꺼내 쓴다.
3. **담당자는 독립 테스트로 자기 모듈을 먼저 완성합니다.** 이후 자신의 개발 브랜치에서 `bootstrap.py`에 등록하고 Stub/Real 혼합 전체 흐름 테스트를 수행합니다. 팀장은 계약 변경 및 PR·최종 통합을 검토합니다. [2단계 개발·테스트](DEVELOPMENT_TEST_FLOW.md)

`Stub`은 입력과 출력 계약을 지키면서 가짜 결과를 제공하는 대체 구현이다. 실제 기능이 아직 없을 때 다른 모듈 개발을 막지 않기 위해 유지한다.

## 1. 파일부터 찾기 — 어디를 열고 어디를 수정하나요?

프로젝트 루트(`pyproject.toml`이 있는 폴더)에서 시작한다.

| 담당 | 먼저 읽기(공통 규칙) | 실제 구현 위치 | 테스트 위치 | 공개 반환값 |
|---|---|---|---|---|
| UI | `core/interfaces.py`의 `ApplicationService` | `src/video_assistant/ui/app.py`·`components.py` | `tests/unit/` 또는 UI 검증 | UI는 `ApplicationService` 결과를 **조회해 표시**, 모듈 출력 직접 생성 X |
| 음성 인식 | `core/models.py`의 `Transcript` | `src/video_assistant/transcription/whisper.py` | `tests/contract/`, `tests/unit/` | `Transcript` |
| 내용 분석 | `core/models.py`의 `VideoAnalysis` | `src/video_assistant/analysis/llm.py` | `tests/contract/`, `tests/unit/` | `VideoAnalysis` |
| 검색·추천 | `core/models.py`의 `RecommendationResult`·`ClipSelection` | `src/video_assistant/recommendation/llm.py` | `tests/contract/`, `tests/unit/` | `RecommendationResult` |
| 영상 편집 | `core/models.py`의 `RenderResult` | `src/video_assistant/editing/ffmpeg.py` | `tests/integration/`, `tests/unit/` | `RenderResult` |
| 팀장/공통 | `core/models.py`, `core/interfaces.py`, `core/workflow.py` | `src/video_assistant/bootstrap.py` 및 합의한 `core/` 파일 | 전체 테스트 | 전체 구성 및 검증 |

> 파일 경로에서 `core/`와 `ui/`는 모두 `src/video_assistant/` 아래에 있다. 기존 Stub(`*/stub.py`)은 **교체하지 말고 유지**한다. 예를 들어 추천 담당자는 기존 `recommendation/keyword.py`가 동작하는 예제이고 `recommendation/llm.py`가 최종 구현 자리다.

## 2. 실제 연결 흐름 — 내 `return`이 어디로 가나요?

```
Streamlit ui/app.py
  └─ app.submit_prepare(video_id)                   -> JobStatus(queued)
       └─ 내부 Worker / core/workflow.py
            ├─ transcriber.transcribe(video)        -> Transcript
            │    └─ 결과 참조/범위 검사 -> store.save_transcript(...)
            └─ analyzer.analyze(transcript)         -> VideoAnalysis
                 └─ 결과 참조/범위 검사 -> store.save_analysis(...)

Streamlit ui/app.py
  └─ app.submit_recommend(SearchRequest)            -> JobStatus(queued)
       └─ core/workflow.py : 저장된 Transcript / VideoAnalysis 조회
            └─ recommender.recommend(request, transcript, analysis)
                 └─ RecommendationResult 반환
                      └─ _check_recommendation(...) 검사
                           └─ store.save_recommendation(result)
                                └─ Worker가 result.id를 JobStatus.result_ref에 기록
                                     └─ UI가 app.get_job(job.id) 조회
                                          └─ UI가 app.get_recommendation(result_ref) 조회
                                               └─ 사용자가 app.create_plan(result.id)
                                                    └─ PlanService -> EditPlan(DRAFT)
                                                         └─ app.revise_plan(...) / approve_plan(...)
                                                              └─ app.submit_render(plan.id, plan.version)
                                                                   └─ editor.render(video, approved_plan, path)
                                                                        └─ RenderResult -> 검사/저장 -> 다운로드
```

**결과 객체와 작업 객체는 다르다.** `recommend()`는 `RecommendationResult`를 직접 반환하지만, UI의 `submit_recommend()`는 백그라운드 작업이므로 우선 `JobStatus`를 반환한다. 완료된 후 `JobStatus.result_ref`(문자열 ID)로 실제 결과를 조회한다. 기능 담당자가 `JobStatus`를 만들어 반환할 필요는 없다.

**다른 모듈의 함수는 호출하지 않는다.** 추천 모듈이 `WhisperTranscriber`나 `LLMContentAnalyzer`를 생성/호출하면 모듈 독립 개발 구조가 무너진다. 추천 모듈에는 이미 준비된 세 입력이 인자로 전달된다.

## 3. 데이터 계약 — 반환 형식이 가장 중요합니다

다음 시그니처는 `core/interfaces.py`에 정의되어 있다. 메서드 인자·반환형을 **임의 변경하지 않는다**.

| 메서드 | 입력 객체 | 정확한 반환 객체 | 반드시 맞아야 하는 관계 |
|---|---|---|---|
| `Transcriber.transcribe(video)` | `VideoAsset` | `Transcript` | `result.video_id == video.id`, `result.transcriber_version == self.VERSION`, 자막 종료시간 <= 영상 길이 |
| `ContentAnalyzer.analyze(transcript)` | `Transcript` | `VideoAnalysis` | `result.video_id == transcript.video_id`, `result.transcript_id == transcript.id`, `result.analyzer_version == self.VERSION`, `topic.segment_ids`는 실제 자막 ID |
| `SegmentRecommender.recommend(request, transcript, analysis)` | `SearchRequest`, `Transcript`, `VideoAnalysis` | `RecommendationResult` | `request_id/video_id/transcript_id/analysis_id`가 원본 입력 ID와 각각 일치, `recommender_version == self.VERSION`, 클립 수 <= `max_clips`, 클립 범위·자막 참조 유효 |
| `VideoEditor.render(video, approved_plan, output_path)` | `VideoAsset`, `ApprovedEditPlan`, `Path` | `RenderResult` | `video_id`, `plan_id`, `plan_version`, `output_path`, `renderer_version` 일치, 실제 MP4 존재·FFprobe 검증 가능 |

### 3.1. 반환 타입은 dict가 아니라 Pydantic 모델입니다

```python
# 올바름: 반환 타입은 RecommendationResult
return RecommendationResult(
    id=uuid4().hex,
    request_id=request.id,
    video_id=request.video_id,
    transcript_id=transcript.id,
    analysis_id=analysis.id,
    clips=tuple(clips),
    recommender_version=self.VERSION,
    is_stub=False,
)
```

`return {"clips": ...}` 처럼 임의의 `dict`를 반환하면 안 된다. `return json.dumps(...)`나 `return result.id`도 안 된다. **저장과 JSON 변환은 공통 `ProjectStore`가 담당**한다. 디버깅 시 `result.model_dump_json(indent=2)`를 호출해 출력 내용을 확인할 수 있다.

Pydantic은 개별 필드 범위·타입을 검증하지만, **입력 객체와 결과 객체 사이의 참조 관계**는 `core/workflow.py`에서 별도로 검증한다. Pydantic 객체를 만들 수 있었다고 통합이 무조건 성공하는 것은 아니다.

### 3.2. 각 모델에서 실제로 필요한 주요 필드

| 출력 모델 | 필드(필수, 별도 표기가 없으면 직접 전달) | 추가 규칙 |
|---|---|---|
| `Transcript` | `id: str`, `video_id: str`, `language: str`, `segments: tuple[TranscriptSegment, ...]`, `transcriber_version: str` | `is_stub: bool=False`, `created_at` 자동; `TranscriptSegment`: `id`, `start_ms`, `end_ms`, `text`; 자막은 시간순/중복 없이 |
| `VideoAnalysis` | `id`, `video_id`, `transcript_id`, `summary: str`, `topics: tuple[TopicSection, ...]`, `analyzer_version` | `TopicSection`: `id`, `title`, `start_ms`, `end_ms`, `segment_ids`; 실제 자막 참조만 사용 |
| `RecommendationResult` | `id`, `request_id`, `video_id`, `transcript_id`, `analysis_id`, `clips: tuple[ClipSelection, ...]`, `recommender_version` | `ClipSelection`: `id`, `start_ms`, `end_ms`, `reason`, `source_segment_ids`; 클립 순서가 편집 순서 |
| `RenderResult` | `id`, `video_id`, `plan_id`, `plan_version`, `output_path: Path`, `duration_ms: int`, `renderer_version` | `is_stub: bool=False`, 실제 파일의 길이와 모델 정보 일치 |

모든 모델은 `core/models.py`가 **정본**이다. 값은 구간 시간에서 반드시 `int` 밀리초로 전달한다: 2.5초는 `2500`이다. `start_ms < end_ms`, `end_ms <= video.duration_ms`, 구간의 끝은 포함하지 않는 `[start_ms, end_ms)` 규칙을 따른다. ID는 안전한 문자열(권장: `uuid4().hex`)을 사용하고, 입력에서 받은 ID를 새로 생성하지 않는다. 새 **결과 객체**나 새 **추천 클립 객체**의 `id`는 새로 생성한다.

**정상 빈 결과**: 무음 영상의 `Transcript.segments=()`와 매칭이 없을 때 `RecommendationResult.clips=()`는 정상이다. 다만 클립이 없는 `EditPlan`은 생성해도 승인할 수 없다. 오류가 났을 때 빈 결과로 위장하지 않는다.

**`VERSION`**: 각 실제 클래스에서 비어 있지 않은 `VERSION = "..."`를 정의한다. 자막·분석 캐시는 구현 버전별로 재사용되므로 모델/프롬프트/결과 해석이 바뀌면 버전을 갱신한다. 현재 추천은 요청마다 재실행되며, `VERSION`은 결과 검증/추적에 이용된다.

### 3.3. RecommendationResult의 JSON 모습 (설명용 예시)

아래는 `RecommendationResult.model_dump(mode="json")` 형태이다. **실제 코드는 JSON을 반환하지 않고 모델을 반환한다.** 여기에 쓴 ID는 예시일 뿐 실제 실행에서는 입력 객체의 ID와 일치시켜야 한다.

```json
{
  "id": "rec001",
  "request_id": "req001",
  "video_id": "video001",
  "transcript_id": "transcript001",
  "analysis_id": "analysis001",
  "clips": [
    {
      "id": "clip001",
      "start_ms": 2666,
      "end_ms": 5333,
      "reason": "AI 활용 사례를 설명하는 자막입니다.",
      "source_segment_ids": ["segment002"]
    }
  ],
  "recommender_version": "keyword-recommender-v1",
  "is_stub": false,
  "created_at": "2026-10-26T00:00:00Z"
}
```

`created_at`은 생략하면 모델 생성 시 자동으로 설정된다. `source_segment_ids`는 실제 `Transcript.segments[*].id` 목록에서만 고른다. **LLM이 직접 생성한 가상의 ID 또는 시간을 그대로 신뢰하지 않는다.** `ClipSelection` 시간은 확인된 자막 구간을 참조하여 계산한다.

## 4. Recommendation 담당자 따라하기 — 현재 소스 기준

### 4.1. 먼저 세 파일을 순서대로 읽습니다

1. `src/video_assistant/core/interfaces.py`에서 `SegmentRecommender`의 `recommend()` 시그니처 확인
2. `src/video_assistant/core/models.py`에서 `SearchRequest`, `Transcript`, `VideoAnalysis`, `ClipSelection`, `RecommendationResult` 필드 확인
3. `src/video_assistant/recommendation/keyword.py`에서 이미 동작하는 `KeywordSegmentRecommender` 클래스 확인

**내가 구현할 최종 파일은 `src/video_assistant/recommendation/llm.py`**이다. 처음에는 `keyword.py`처럼 간단한 로직을 참고한 뒤 점차 검색/LLM 로직으로 변경한다. 기존 `stub.py`는 수정하지 않는다.

### 4.2. 알고리즘의 핵심은 `recommend()` 내부입니다

`keyword.py`에는 실제로 아래와 같이 구성되어 있다.

```python
class KeywordSegmentRecommender(SegmentRecommender):
    VERSION = "keyword-recommender-v1"

    def recommend(
        self, request: SearchRequest, transcript: Transcript, analysis: VideoAnalysis
    ) -> RecommendationResult:
        # 실제 후보 검색: 기존 keyword.py 참고
        # 후보를 ClipSelection 객체들로 만들고 아래와 같이 반환
        return RecommendationResult(
            id=uuid4().hex,
            request_id=request.id,
            video_id=request.video_id,
            transcript_id=transcript.id,
            analysis_id=analysis.id,
            clips=tuple(clips),
            recommender_version=self.VERSION,
            is_stub=False,
        )
```

위 코드는 **반환 방식만 보여주는 설명용 발췌**다. 완성된 실행 예제는 `recommendation/keyword.py`에 있고, 학습 테스트는 `tests/contract/test_recommender_keyword.py`에 있다.

추천 알고리즘을 발전시켜도 바깥의 `recommend()` 시그니처와 `return RecommendationResult(...)`는 유지한다. 단계별로는 *키워드 후보 검색 → 자막·주제 활용 → 의미 검색 및 LLM 판단 → 인접 구간 조합·중복 처리 → 추천 이유 → 계약 검증* 순서가 편하다.

### 4.3. 실제로 추천 반환값을 눈으로 보는 명령

환경 설치(`python -m pip install -e ".[test]"`) 후 프로젝트 루트에서 실행한다.

```bash
python scripts/inspect_recommendation_flow.py
```

이 스크립트는 **영상 업로드 → Stub 자막 → Stub 분석 → Keyword 추천 → `RecommendationResult` JSON 출력 → `EditPlan` 생성**을 실제로 수행한다. 출력되는 `RecommendationResult` JSON의 `request_id`, `transcript_id`, `analysis_id`, `clips`를 확인하고, 뒤에 생성되는 `EditPlan.recommendation_id`가 같은 결과의 ID인지 비교해 본다. JSON은 학습을 위해 출력할 뿐, `recommend()`의 반환값은 Pydantic 객체다.

### 4.4. 독립 테스트가 끝난 후 내 브랜치의 `bootstrap.py`에 등록합니다

프로젝트의 `bootstrap.py`에는 현재 아래 레지스트리가 있다.

```python
RECOMMENDERS = {
    "stub": StubSegmentRecommender,
    "keyword": KeywordSegmentRecommender,
}
```

실제 `LLMSegmentRecommender` 구현과 독립 테스트가 끝나면 **담당자가 자신의 브랜치에서** 모듈을 import하고, 예를 들어 다음 항목을 추가한다.

```python
from .recommendation.llm import LLMSegmentRecommender

RECOMMENDERS = {
    "stub": StubSegmentRecommender,
    "keyword": KeywordSegmentRecommender,
    "llm": LLMSegmentRecommender,
}
```

생성자에 API 키나 모델 설정이 필요하면 레지스트리에는 `"llm": lambda: LLMSegmentRecommender(...)` 같은 **인자 없는 팩토리**를 등록한다. 팀원이 내부 구현을 바꿔도 `workflow.py`·`ui/app.py`를 수정하지 않는다.

> `RECOMMENDER_BACKEND=llm`은 클래스가 실제로 등록된 **이후에만** 선택할 수 있다. 현재 바로 실행하면 미등록 오류가 난다. `.env.example`을 `.env`로 복사하면 자동으로 읽는다. [설정 가이드](ENV_CONFIGURATION.md)

### 4.5. 화면에서 연동 확인하기

PowerShell:

```powershell
$env:TRANSCRIBER_BACKEND = "stub"
$env:ANALYZER_BACKEND = "stub"
$env:RECOMMENDER_BACKEND = "keyword"
$env:EDITOR_BACKEND = "stub"
python -m streamlit run src/video_assistant/ui/app.py
```

macOS/Linux:

```bash
RECOMMENDER_BACKEND=keyword python -m streamlit run src/video_assistant/ui/app.py
```

`examples/demo.mp4` 업로드 → **영상 등록** → **영상 준비 작업 시작** → 검색창에 `AI 활용` → **구간 추천 요청** → 추천 결과 표시 → **추천 결과로 편집 계획 생성** 순서로 확인한다. 기존 Streamlit 세션의 캐시된 서비스를 피하려면 설정을 바꾼 후 앱 프로세스를 재시작한다.

### 4.6. 테스트는 어떤 단계에서 확인하나요?

```bash
# 담당 기능 계약 + 기존 전체 테스트
python -m pytest -q tests/contract/test_recommender_keyword.py
python -m pytest -q

# 프로젝트 전체 Stub 경로 (환경변수와 관계없이 Stub 사용)
python scripts/smoke_test.py
```

추가로 `tests/contract/test_recommender_keyword.py`를 참고해 **자신의 구현 전용 계약 테스트**를 만든다. `Settings(runtime_dir=tmp_path, recommender_backend="llm")` 형태로 해당 구현체를 지정하고, `app.submit_prepare()` 뒤 `app.submit_recommend()`를 호출해 작업 종료 후 결과를 조회한다.

최소 테스트: 정상 결과 / 검색 결과 없음 / `max_clips` 상한 / 시간 범위 / 잘못된 자막 ID / `VERSION` 불일치 / LLM 호출 실패. 결과가 유효하지 않으면 정상 완료가 아니라 `JobState.FAILED`가 되어야 한다. LLM 품질 평가는 별도로 샘플 요청·정답 구간과 비교한다.

## 5. 나머지 담당자도 동일한 방식으로 연결됩니다

### 음성 인식

- **입력**: `video: VideoAsset` (`source_path`, `duration_ms`, `has_audio` 등 사용)
- **반환**: `Transcript(id=새 ID, video_id=video.id, language="ko", segments=..., transcriber_version=self.VERSION, is_stub=False)`
- **검증**: 구간 시간순/중복 없음, 각 `end_ms` <= `video.duration_ms`, `video_id`와 `VERSION` 정확히 일치
- **다음 단계**: 공통 Workflow가 자막을 저장하고 이를 `analyzer.analyze(transcript)`에 전달
- **등록**: `TRANSCRIBERS["whisper"] = WhisperTranscriber` 같은 방식

### 영상 내용 분석

- **입력**: `transcript: Transcript`
- **반환**: `VideoAnalysis(id=새 ID, video_id=transcript.video_id, transcript_id=transcript.id, summary=..., topics=..., analyzer_version=self.VERSION, is_stub=False)`
- **검증**: `TopicSection.segment_ids`는 자막에 실제 존재하는 ID이며, 주제 구간도 원본 영상 길이 이내
- **다음 단계**: Workflow가 분석 결과를 저장하고 Recommendation 요청 때 `transcript`와 함께 조회
- **등록**: `ANALYZERS["llm"] = LLMContentAnalyzer` 같은 방식

### 영상 편집

- **입력**: `video: VideoAsset`, `plan: ApprovedEditPlan`, `output_path: Path`
- **반환**: `RenderResult(id=새 ID, video_id=video.id, plan_id=plan.id, plan_version=plan.version, output_path=output_path, duration_ms=실제 측정한 길이, renderer_version=self.VERSION, is_stub=False)`
- **검증**: 실제 `output_path`에 유효한 MP4 생성; FFprobe 측정 길이와 반환 길이 차이가 100ms를 넘지 않아야 함(현재 공통 검사 기준). 구간 선택에 따른 재생 시간 정확도는 별도의 렌더링 테스트에서 검증
- **다음 단계**: Workflow가 결과를 저장하고 UI가 재생·다운로드
- **등록**: `EDITORS["ffmpeg"] = FFmpegVideoEditor` 같은 방식

### UI

- **호출 대상**: `ApplicationService` (`app.ingest`, `app.submit_prepare`, `app.submit_recommend`, `app.get_job`, `app.get_recommendation`, `app.create_plan`, `app.revise_plan`, `app.approve_plan`, `app.submit_render`, `app.get_render_result`)
- **주의**: UI에서 `recommender.recommend()`나 FFmpeg 등을 직접 호출하지 않는다. `submit_*`는 비동기 작업 상태(`JobStatus`)를 먼저 반환하므로, `SUCCEEDED` 이후 `result_ref`를 조회해야 한다.

## 6. Git과 팀장 통합 순서

1. 팀원: 자기 실제 클래스와 단위/계약 테스트 구현. `core` 또는 타 담당자의 실제 구현체를 임의로 수정하지 않는다.
2. 팀원: PR에 수정 파일, 입력·출력 계약 준수 여부, 백엔드 키, `VERSION`, 필요한 의존성/환경변수, 테스트 결과를 기록한다.
3. 팀장: 공통 계약 변경 요구를 검토하고 관련 담당자에게 공유한다. 필요시 공통 모델·Stub·테스트·문서를 함께 변경한다.
4. 팀원: 독립 테스트가 통과한 뒤 **자기 브랜치에서** `bootstrap.py`의 해당 레지스트리에 실제 클래스를 등록한다.
5. 팀원: 내 구현 하나만 Real로 선택하고 나머지는 Stub로 유지해 전체 흐름 테스트를 수행한다. 구현·등록·테스트를 함께 PR로 제출한다.
6. 팀장 및 담당자: 계약·의존성·비밀키 설정을 검토하고 main 병합 후 회귀 테스트한다. 준비된 모듈부터 Real 조합과 품질을 최종 검증한다.

**Git 충돌이 없다는 것은 결과 모델이 연결된다는 뜻이 아니다.** 병합 후 입력/출력 참조 규칙과 전체 사용자 흐름을 재검증한다.

## 7. 연결이 안 되면 어디부터 찾을까요?

| 증상 | 먼저 확인할 부분 |
|---|---|
| `구현 'llm'은 아직 등록되지 않았습니다` | `bootstrap.py` 레지스트리와 선택한 `*_BACKEND` 환경변수 |
| `AttributeError` / 타입 관련 오류 | `return`이 dict나 문자열이 아닌 정확한 Pydantic 출력 모델인지 확인 |
| 작업이 `FAILED`이고 `recommendation_failed` | `result.request_id`, `video_id`, `transcript_id`, `analysis_id`, `recommender_version`, clip 범위/참조 검사 |
| `자막/분석을 먼저 완료해 주세요` | `submit_prepare()` 결과를 기다렸는지, 현재 backend `VERSION`의 캐시가 존재하는지 |
| 추천 결과가 항상 같은 구간 | 현재 `RECOMMENDER_BACKEND=stub`인지 확인; Keyword/LLM 연결 여부 확인 |
| 추천이 0개라서 승인 실패 | 빈 추천 결과는 정상이나, 빈 편집 계획은 승인할 수 없음 |
| 화면에 바꾼 구현이 안 보임 | PowerShell 환경변수의 현재 터미널 적용 여부, Streamlit 재시작/공유 캐시 확인 |
| `ffprobe` 실행 불가 | OS에서 FFmpeg/FFprobe를 별도 설치하고 `PATH`에 등록했는지 확인 |

## 8. 담당자 완료 체크리스트

- [ ] 내 구현 클래스가 맞는 ABC를 상속하고 메서드를 구현한다.
- [ ] 반환값이 정확한 Pydantic 모델 객체다 (`return ...Result(...)`).
- [ ] `VERSION` 문자열이 있고 결과의 버전 필드와 일치한다.
- [ ] 입력에서 받은 참조 ID를 결과에 정확히 보존한다.
- [ ] 모든 시간은 밀리초 정수이며 유효한 구간이다.
- [ ] 정상/빈 결과/실패를 구분하고 계약 테스트를 통과한다.
- [ ] Stub과 내 실제 구현을 각각 선택해 실행할 수 있다.
- [ ] 독립 테스트 완료 후 내 브랜치의 `bootstrap.py`에 등록했고 Stub/Real 혼합 전체 흐름 테스트를 통과했다.

다른 모듈과 이어지는 **유일한 접점은 공통 인터페이스의 입력/출력 계약**이다. 해당 계약을 지키면 동료의 알고리즘과 무관하게 독립 개발하고, 준비된 모듈부터 교체·통합할 수 있다.
