# 담당자별 개발 업무 매뉴얼 v0.1 — Input/Output 계약 기반

> **문서 길잡이:** 처음 보는 분은 [시작 가이드](START_HERE.md) → [내 담당 작업](ROLE_IMPLEMENTATION_MANUAL.md)을 먼저 읽으세요. 이 문서는 **필요한 세부 사항을 확인할 때** 사용하는 참고자료입니다.


> **대상:** 5인 팀(팀장도 5명 중 한 명).  
> **시작 전에 반드시 읽기:** [INPUT_OUTPUT_CONTRACT_V1.md](INPUT_OUTPUT_CONTRACT_V1.md).  
> **작업 전제:** `core/`/`bootstrap.py`와 네 기능 Stub이 실행 가능한 상태. 실제 Whisper/LLM/FFmpeg 편집은 아직 미구현.

## 1. 개발자가 실제로 하는 일: 5단계

1. **내가 받은 Input 확인:** `core/interfaces.py`의 시그니처와 `core/models.py`의 입력 모델을 읽는다.
2. **정해진 Output 확인:** 출력 모델에서 꼭 채울 필드/ID·시간 규칙을 체크한다.
3. **나의 구현 파일에 코드 작성:** 내부 알고리즘은 자유롭지만 입력·출력 계약은 변경하지 않는다. 기존 `*/stub.py`는 유지한다.
4. **독립 테스트:** 선행 담당자의 실제 구현을 기다리지 않고 `tests/fixtures/contract_samples.py`의 입력으로 자신의 코드를 직접 테스트한다.
5. **전체 연결 테스트:** **독립 테스트와 기능 품질 확인을 마친 뒤**, 담당자가 자신의 브랜치의 `bootstrap.py`에 직접 등록한다. 내 구현만 실제로 선택하고 다른 모듈은 Stub으로 실행·검증한다.
6. **PR 제출:** 구현 파일, 등록 코드, 독립·전체 흐름 테스트 결과를 함께 제출한다. 팀장은 공통 계약과 병합을 검토한다.

```text
[선행 단계 Stub 또는 고정 Fixture] --Input--> [내 모듈의 공개 메서드]
                                                       |
                                                     Output
                                                       |
                             [Workflow 검증] -> [ProjectStore] -> [다음 단계]
```

## 2. 담당 파일 지도

| 담당 | 내 구현 파일 | 내가 참고할 Stub/예시 | 내가 추가할 테스트 | 내가 반환할 객체 |
|---|---|---|---|---|
| UI/UX | `src/video_assistant/ui/app.py`, `components.py` | Streamlit 기존 화면, `ApplicationService` | `tests/unit/test_ui_*.py` + 수동 전체 흐름 | UI는 서비스 객체 조회·표시 |
| 음성 인식 | `src/video_assistant/transcription/whisper.py` | `transcription/stub.py`, `sample_video()` | `tests/contract/test_whisper_contract.py` | `Transcript` |
| 내용 분석 | `src/video_assistant/analysis/llm.py` | `analysis/stub.py`, `simple.py`, `sample_transcript()` | `tests/contract/test_analysis_llm_contract.py` | `VideoAnalysis` |
| 검색·추천 | `src/video_assistant/recommendation/llm.py` | `recommendation/stub.py`, `keyword.py`, `sample_transcript()/sample_analysis()` | `tests/contract/test_recommendation_llm_contract.py` | `RecommendationResult` |
| 영상 편집 | `src/video_assistant/editing/ffmpeg.py` | `editing/stub.py`, `sample_video()/sample_approved_plan()` | `tests/integration/test_ffmpeg_real.py` | `RenderResult` |
| 팀장/공통 | `src/video_assistant/core/`, `bootstrap.py` | 계약 명세서, 기존 Stub/Fixture | `tests/contract/`, `tests/integration/` | 계약·저장·작업 연결 관리 |

**공통 파일은 담당자 모두가 수정하는 공간이 아니다.** 변경이 필요하면 팀장에게 계약 변경 요청을 보낸다. 실제 팀원 본인의 구현 파일에는 원하는 보조 파일(`prompts.py`, `search.py` 등)을 추가해도 된다.

## 3. 담당자 1 — UI/UX

**입력:** 사용자가 업로드한 MP4, 검색어, 클립 수정값. 공통 `ApplicationService`가 반환한 `JobStatus`, `Transcript`, `VideoAnalysis`, `RecommendationResult`, `EditPlan`, `RenderResult`.

**해야 할 일:**

- 업로드 후 `app.ingest(...)`, 준비 작업 `app.submit_prepare(video_id)`, 추천 `app.submit_recommend(SearchRequest(...))` 호출
- `get_job(job.id)`로 `QUEUED/RUNNING/SUCCEEDED/FAILED` 구분, 완료 후 `result_ref`로 결과 조회
- 자막·주제·추천 시간과 이유 표시, 계획 수정·승인 버튼 구현
- 렌더 결과 다운로드; 결과의 `is_stub`가 참이면 가짜 결과임을 명시
- 잘못된 입력·작업 실패·무추천·무음 UI 상태 각각 테스트

**하지 않을 일:** 직접 FFmpeg/Whisper/LLM 호출, `EditPlan.status` 강제 갱신, 저장소 JSON 직접 수정, 다른 담당자 반환 모델 재정의.

**선행 의존성 대체:** 모든 백엔드를 `stub`으로 켜고 전체 화면을 만든다. 예제 `examples/demo.mp4`로 업로드를 검증한다.

**완료 기준:** Stub만으로 업로드→준비→추천→수정/승인→원본 복사 Stub 결과까지 진행하고, 실패·빈 결과를 구분해 보여준다.

## 4. 담당자 2 — 음성 인식

**구현 클래스:** `WhisperTranscriber(Transcriber)`, `VERSION = "whisper-..."`  
**함수:** `transcribe(video: VideoAsset) -> Transcript`

**Input 필수 정보:** `video.id`, `video.source_path`, `video.duration_ms`, `video.has_audio`.

**내부 작업:** 오디오 추출/모델 호출 → 문장 및 타임스탬프 추출 → ms 정수 변환/정렬 → `TranscriptSegment` 목록 구성 → `Transcript` 반환.

**Output 최소 예시:**

```python
return Transcript(
    id=uuid4().hex, video_id=video.id, language="ko",
    segments=tuple(segments), transcriber_version=self.VERSION, is_stub=False,
)
```

**다음 모듈에서 사용:** 분석 담당자가 `Transcript.segments[*].text`로 주제 분석, 추천 담당자가 `id/start_ms/end_ms/text`로 추천 근거 및 편집 시간 결정.

**선행 Stub:** 파일 입력은 `sample_video()`가 제공. 전체 실행에서는 업로드 서비스와 FFprobe가 입력 모델을 생성한다.

**테스트:** 무음 → `segments=()` / 정상 음성 → 비어 있지 않은 자막 / 시간 역전·중첩 없음 / `video_id`, `VERSION` 일치 / 실제 자막 품질은 별도 수동 검증.

## 5. 담당자 3 — 영상 내용 분석

**구현 클래스:** `LLMContentAnalyzer(ContentAnalyzer)`, `VERSION = "llm-analyzer-..."`  
**함수:** `analyze(transcript: Transcript) -> VideoAnalysis`

**Input:** 자막 전체 ID와 언어, 각 자막의 ID/시간/내용. 이전 음성 인식 담당자 완료 불필요.

**내부 작업:** 자막 문맥 분석·주제 선정·긴 입력 분할/결과 병합·LLM 응답 파싱 → 원본 자막 ID와 연결한 `TopicSection` 생성.

**Output 최소 예시:**

```python
return VideoAnalysis(
    id=uuid4().hex, video_id=transcript.video_id, transcript_id=transcript.id,
    summary=summary, topics=tuple(topics),
    analyzer_version=self.VERSION, is_stub=False,
)
```

**다음 모듈에서 사용:** 추천 담당자가 `analysis.summary`, `topics[*].segment_ids`로 검색 후보를 찾는다. UI는 전체 요약을 표시한다.

**선행 Stub/Fixture:** `sample_transcript()` 또는 `StubTranscriber().transcribe(sample_video())`로 입력을 얻는다. 외부 Whisper 호출 불필요.

**테스트:** 빈 자막 → 빈 주제 / 주제 시간/자막 참조 존재 / `transcript_id` 전달 정확 / 비정상 LLM JSON·API 실패 처리 / 길고 복잡한 자막에서 분석 품질 확인.

## 6. 담당자 4 — 자연어 검색·추천

**구현 클래스:** `LLMSegmentRecommender(SegmentRecommender)`, `VERSION = "llm-recommender-..."`  
**함수:** `recommend(request: SearchRequest, transcript: Transcript, analysis: VideoAnalysis) -> RecommendationResult`

**Input:** `request.query/max_clips/video_id`, 자막의 ID/시간/텍스트, 분석의 요약/주제/참조 ID.

**내부 작업:** 사용자 요청 해석 → 자막/주제 후보 탐색 → 의미적 관련성 판단 → 원본 자막의 ID로 시간 확정 → 중복 제거·편집 순서 제안 → 추천 이유.

**Output 최소 예시:**

```python
clips = (
    ClipSelection(
        id=uuid4().hex, start_ms=2000, end_ms=5000,
        reason="자동화를 설명하는 발언", source_segment_ids=("fixture-s2",),
    ),
)
return RecommendationResult(
    id=uuid4().hex, request_id=request.id, video_id=request.video_id,
    transcript_id=transcript.id, analysis_id=analysis.id,
    clips=clips, recommender_version=self.VERSION, is_stub=False,
)
```

위 예시는 **고정 Fixture의 `fixture-s2`를 사용할 때에만** 참조 ID/시간이 올바르다. 실제 개발 코드는 `transcript.segments`에서 구간을 찾아 시간·ID를 복사해야 하며, 샘플 값을 하드코딩하지 않는다.

**다음 모듈에서 사용:** `PlanService.create_draft(result.id)`가 `result.clips`를 편집 계획으로 만들고, 사용자 수정·승인 후 영상 편집기가 순서대로 잘라낸다.

**선행 Stub/Fixture:** `sample_request()`, `sample_transcript()`, `sample_analysis()`. 음성/분석 실구현이 없어도 `recommend(...)` 직접 호출 가능. 전체 프로그램에서는 `TRANSCRIBER_BACKEND=stub`, `ANALYZER_BACKEND=stub` 조합.

**테스트:** 검색 결과 있음/없음, `max_clips`, 시간·원본 자막 ID, 배열 순서, LLM 참조 조작/잘못된 JSON/API 실패, 실제 요청에 대한 추천 관련성 평가.

## 7. 담당자 5 — FFmpeg 영상 편집

**구현 클래스:** `FFmpegVideoEditor(VideoEditor)`, `VERSION = "ffmpeg-editor-..."`  
**함수:** `render(video: VideoAsset, plan: ApprovedEditPlan, output_path: Path) -> RenderResult`

**Input:** 원본 MP4 경로·길이·오디오 유무, `plan.clips`의 `[start_ms,end_ms)`와 배열 순서, 공통 서비스가 지정한 출력 경로.

**내부 작업:** FFmpeg 인자 배열로 구간 추출 및 연결, 인코딩, 출력 생성, FFprobe 재검증, 임시 파일 정리.

**Output 최소 예시:**

```python
return RenderResult(
    id=uuid4().hex, video_id=video.id, plan_id=plan.id,
    plan_version=plan.version, output_path=output_path,
    duration_ms=actual_duration_ms, renderer_version=self.VERSION,
    is_stub=False,
)
```

**다음 모듈에서 사용:** 공통 Workflow가 결과 경로/계획 ID/버전·실제 파일 길이를 확인한 후 저장, UI가 다운로드한다.

**선행 Stub/Fixture:** `sample_video()` + `sample_approved_plan()`. 내용 분석이나 검색 실구현을 실행할 필요 없음.

**테스트:** 실제 영상에서 2개 클립이 정확한 순서로 합쳐지는지 검증. Stub 편집기는 **원본 복사만** 하므로 실제 컷 검증으로 오해하지 않는다.

## 8. 팀장 — 계약 관리 및 통합 검토

1. 각 담당자가 제안한 필요한 Input/Output 변경을 **다음 소비 모듈과 함께** 검토한다.
2. 계약 수정이 승인되면 `core/models.py`/`interfaces.py` 및 Fixture/Stub/계약 테스트/문서를 같은 변경에서 정합성 있게 수정한다.
3. 담당자는 독립 테스트를 통과한 후 **자기 브랜치에서** `src/video_assistant/bootstrap.py`에 인자 없는 클래스/팩토리를 등록하고 혼합 Stub/Real 테스트를 수행한다.
4. 팀장은 구현·등록·테스트를 포함한 PR을 검토한다. 필요한 라이브러리·API 키 설정, 재시도/오류 동작을 확인한다.
5. `main` 병합 전후 전체 자동 테스트를 실행하고, Streamlit 업로드부터 다운로드까지 수동으로 확인한다.

레지스트리 예시(기존 코드의 해당 부분만):

```python
# 실제 구현 등록 후 (예시)
RECOMMENDERS = {
    "stub": StubSegmentRecommender,
    "keyword": KeywordSegmentRecommender,
    "llm": build_llm_recommender,
}
```

API 키와 모델명을 필요로 하면 팩토리 `build_llm_recommender()` 안에서 안전하게 주입한다. 팀원은 다른 담당자의 구현을 직접 import하지 않는다. `bootstrap.py`는 전체 조립을 담당한다.

## 9. 실제 개발 검증 절차

```bash
# 1. 공통 계약·Fixture 확인
python -m pytest -q tests/contract/test_module_io_contracts.py

# 2. 실제 백엔드 일부 교체와 혼합 실행 확인
python -m pytest -q tests/integration/test_contract_stub_matrix.py

# 3. 전체 회귀 테스트
python -m pytest -q

# 4. 데이터 객체 인계 순서 확인
python scripts/show_contract_chain.py

# 5. 전체 Stub 흐름
python scripts/smoke_test.py

# 6. UI 직접 실행
python -m streamlit run src/video_assistant/ui/app.py
```

**Windows PowerShell에서 추천만 실습용 Keyword로 선택:**

```powershell
$env:TRANSCRIBER_BACKEND = "stub"
$env:ANALYZER_BACKEND = "stub"
$env:RECOMMENDER_BACKEND = "keyword"
$env:EDITOR_BACKEND = "stub"
python -m streamlit run src/video_assistant/ui/app.py
```

설정을 변경한 뒤 Streamlit을 재시작한다. 프로젝트 루트의 `.env`는 자동으로 읽으며, PowerShell `$env:` 지정 값이 우선한다. [설정 가이드](ENV_CONFIGURATION.md)

## 10. PR 제출 체크리스트 / Definition of Done

- [ ] 내 클래스가 `core/interfaces.py`의 공개 ABC를 구현한다.
- [ ] Input과 Output의 **정확한 Pydantic 모델**을 사용한다. `dict`, JSON 문자열만 반환하지 않는다.
- [ ] 출력의 `video_id`·상위 결과 ID·`VERSION`이 입력과 일치한다.
- [ ] 영상 시간은 밀리초 정수이며 원본 길이 이내다.
- [ ] 정상, 빈 결과, 실패 시나리오를 각각 검증했다.
- [ ] 선행 구현이 없어도 공통 Fixture로 내 함수를 직접 테스트할 수 있다.
- [ ] Stub과 내 구현이 `bootstrap.py`에서 교체 가능하다.
- [ ] 기능 품질이 필요한 모듈은 실제 미디어/샘플 요청으로 별도 검증했다.
- [ ] 공통 모델·환경설정 변경 시 관련 담당자와 합의했고 문서/Fixture/테스트를 갱신했다.
- [ ] PR의 변경 파일, 테스트 명령, 결과, 알려진 제한을 기록했다.

**코드 결합의 완료 기준은 단순히 Git merge 성공이 아니다.** `Stub + 새 구현체` 조합과 전체 사용자 흐름에서 입력/출력 계약이 유지되는 것까지 확인해야 한다.
