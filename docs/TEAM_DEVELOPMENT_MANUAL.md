# AI 영상편집 어시스턴트 — 팀 개발 기본 매뉴얼

> **문서 길잡이:** 처음 보는 분은 [시작 가이드](START_HERE.md) → [내 담당 작업](ROLE_IMPLEMENTATION_MANUAL.md)을 먼저 읽으세요. 이 문서는 **필요한 세부 사항을 확인할 때** 사용하는 참고자료입니다.


> **문서 버전:** v1.1 (검토·수정용 초안)  
> **적용 기준:** `video_assistant_skeleton_v1` 스켈레톤  
> **기술 스택:** Python 3.11+, Streamlit, Pydantic v2, FFmpeg/FFprobe, 애플리케이션 내부 작업자  
> **대상:** UI, 음성 인식, 내용 분석, 검색·추천, 영상 편집 담당자 5명 및 그중 1명인 팀장

## 먼저 읽을 문서 — 개발 후 언제 연결하나요?

**[DEVELOPMENT_TEST_FLOW.md](DEVELOPMENT_TEST_FLOW.md)**에서 독립 테스트 → 완성 후 전체 흐름 테스트를 먼저 확인하세요. 연결 세부사항은 **[MODULE_INTEGRATION_GUIDE.md](MODULE_INTEGRATION_GUIDE.md)**를 참고하세요. 담당자가 구현해야 할 메서드, `return`할 Pydantic 결과의 필드, `bootstrap.py` 등록, UI/Worker/Storage까지 이어지는 실제 흐름, 테스트 및 디버깅 절차를 모아서 설명합니다.

## 1. 이 문서의 목적과 개발 순서

이 프로젝트는 **공통 실행 골격을 먼저 마련한 뒤, 5명이 각 기능을 독립적으로 구현하고, 실제 구현을 하나씩 통합**한다.

초기 `main`에는 공통 모델/인터페이스/오류, 저장, 편집 계획 관리, 작업 스케줄러, 워크플로, Streamlit 기본 UI, 각 모듈의 Stub이 들어 있다. 실제 Whisper·LLM·FFmpeg 편집은 각 기능 담당자가 완성한다.

- **담당자:** 본인 영역의 실제 구현을 Fixture로 독립 테스트하고, 기능이 준비되면 자기 브랜치의 `bootstrap.py`에 등록해 다른 Stub과 전체 흐름을 검증한 후 PR을 제출한다.
- **팀장:** 공통 계약 변경 및 구현체 등록 PR을 검토하고, `main` 병합과 최종 통합을 관리한다.
- **공동 책임:** 모든 실제 구현이 조합된 전체 흐름, 결과 품질, 예외 사례를 최종 검증한다.

> **주의:** 팀장은 5명 중 한 명이다. 공통 기능 개선을 전부 팀장 혼자 맡는다는 의미가 아니다. 공통 파일의 추가 작업은 팀 내에서 명시적으로 배정한다.

## 2. 디렉터리와 수정 권한

```text
video_assistant_skeleton_v1/
├── README.md
├── pyproject.toml                   # 공통 의존성, 테스트 설정
├── .env.example                     # 실제 사용할 .env 파일의 복사용 예시
├── src/video_assistant/
│   ├── bootstrap.py                 # [담당자 등록 / 팀장 검토] 구현체 선택·연결
│   ├── core/
│   │   ├── models.py                # [공통 계약] Pydantic 모델
│   │   ├── interfaces.py            # [공통 계약] ABC 공개 인터페이스
│   │   ├── errors.py                # [공통 계약] AppError / ErrorCode
│   │   ├── config.py                # [공통] 실행 설정
│   │   ├── media.py                 # [공통] FFprobe 유틸리티
│   │   ├── storage.py               # [공통] 파일·JSON 저장
│   │   ├── plan_service.py          # [공통] 계획 수정·승인
│   │   ├── jobs.py                  # [공통] 내부 작업자·작업 상태
│   │   └── workflow.py              # [공통] 전체 단계 연결
│   ├── ui/
│   │   ├── app.py                   # [담당 1] Streamlit 화면
│   │   └── components.py            # [담당 1] 재사용 UI
│   ├── transcription/
│   │   ├── stub.py                  # 기존 더미 구현
│   │   └── whisper.py               # [담당 2] 실제 Whisper
│   ├── analysis/
│   │   ├── stub.py                  # 기존 더미 구현
│   │   └── llm.py                   # [담당 3] 실제 영상 내용 분석
│   ├── recommendation/
│   │   ├── stub.py                  # 기존 더미 구현
│   │   └── llm.py                   # [담당 4] 실제 검색·추천
│   └── editing/
│       ├── stub.py                  # 기존 더미 구현
│       └── ffmpeg.py                # [담당 5] 실제 구간 편집
├── tests/
│   ├── contract/                    # 공개 계약 검증
│   ├── unit/                        # 개별 모듈 단위 테스트
│   └── integration/                 # 결합 테스트
├── examples/demo.mp4               # 개발용 예제 영상
└── runtime/                        # 실행 산출물(Git 제외)
```

**수정 원칙**

1. 각 담당자는 자기 디렉터리와 해당 테스트 파일을 주로 수정한다. 본인 모듈 내 추가 파일 생성은 허용한다.
2. `core/models.py`, `core/interfaces.py`, `core/errors.py`, `core/config.py`, `bootstrap.py`, `pyproject.toml`, 공통 Fixture의 변경은 사전에 공유하고 검토한다.
3. 다른 모듈 구현체를 직접 import하거나 수정해 우회 연결하지 않는다.
4. 이미 제공된 `stub.py`는 공통 연동의 기준이다. Stub을 변경하려면 기존 통합 테스트 영향도 함께 확인한다.
5. 기능 구현이 끝났다는 사실과 `main`에 등록·통합되었다는 사실은 구분한다.

## 3. 모든 담당자가 지켜야 할 공통 계약

- `src/video_assistant/core/interfaces.py`에 있는 공개 ABC의 메서드 이름·입력·반환형을 지킨다.
- 결과는 `core/models.py`의 **Pydantic 모델 인스턴스**로 반환한다. 모듈 간에 임의의 `dict` 포맷을 전달하지 않는다.
- 영상 구간의 시간은 **정수 밀리초**, 구간은 `[start_ms, end_ms)`, `start_ms < end_ms`이다.
- 처리 결과의 `video_id`, `transcript_id`, `analysis_id`, `request_id`, `plan_id` 등 참조값은 실제 입력과 일치해야 한다.
- 각 실제 구현 클래스에 **`VERSION` 문자열**을 정의한다. 모델·프롬프트·후처리 규칙 등 결과 의미가 변하면 버전 변경을 검토한다. 영상 준비 캐시는 `VERSION`으로 구별된다.
- 실제 결과의 `is_stub`는 `False`, 더미 결과는 `True`로 구별한다.
- 정상적인 빈 결과와 실패를 구분한다. 자막이 없는 경우 `Transcript.segments=()`, 검색 결과가 없으면 `RecommendationResult.clips=()`를 허용한다.
- 오류는 가능한 한 `AppError`와 `ErrorCode`로 변환하고, API 키나 민감한 원문을 사용자 오류 메시지에 노출하지 않는다.
- 기본 공개 메서드는 **동기식**이다. 장시간 작업의 스레드 실행과 상태 저장은 `core/jobs.py`와 `core/workflow.py`가 처리한다. 팀원 모듈에서 Streamlit 함수를 호출하지 않는다.
- 코드 전체를 통합 실행할 때 임의의 스크립트·셸 문자열 실행을 허용하지 않는다. 사용자 입력을 명령어 코드로 취급하지 않는다.

## 4. 담당자별 개발 지침

### 담당 1 — UI / UX

**수정 위치**: `src/video_assistant/ui/app.py`, `components.py`; 추가 테스트 `tests/unit/test_ui.py` 등.

**수행 작업**: 영상 업로드, 자막/분석 결과 표시, 자연어 요청 입력, 추천 구간 및 근거 표시, 클립 시간·순서 수정, 편집 계획 승인, 작업 상태/실패 표시, 결과 재생·다운로드 화면 개선.

**연결 규칙**: `ApplicationService`만 사용한다. `WhisperTranscriber`, `LLMContentAnalyzer`, `FFmpegVideoEditor` 같은 실제 클래스를 UI에서 직접 생성하거나 호출하지 않는다. `st.session_state`는 화면의 현재 선택과 작업 ID 등을 보관하는 데 사용하며 승인 여부·계획 유효성의 최종 판단은 `PlanService`에 맡긴다. `st.cache_resource`로 공유하는 서비스는 앱 인스턴스 하나를 전제로 한다.

**완료 기준**: 다른 네 기능이 모두 Stub이어도 사용자 흐름이 끝까지 동작하고, 빈 결과·작업 실패·오래된 계획 버전 충돌을 사용자에게 설명할 수 있다.

### 담당 2 — 음성 인식 / 자막 생성

**수정 위치**: `src/video_assistant/transcription/whisper.py` 및 해당 모듈 내부 보조 파일; `tests/contract/test_transcriber.py`, 관련 단위 테스트.

**구현 클래스·계약**: `WhisperTranscriber(Transcriber)` / `transcribe(self, video: VideoAsset) -> Transcript` / `VERSION` 필수.

**수행 작업**: 영상 오디오 추출, Whisper 인식, 언어 및 자막 구간 생성, 초 단위 출력의 정수 ms 변환, 구간 정렬, 무음 처리, 호출/모델 오류 처리. 별도의 SRT 내보내기 기능을 추가한다면 `Transcript` 데이터와의 일관성을 보장하고 공통 저장 기능과 책임을 협의한다.

**검증**: `Transcript.video_id == video.id`, `Transcript.transcriber_version == VERSION`, 모든 구간이 영상 길이 내에 있고 시간순·비중첩이며 자막 ID가 유일해야 한다. 무음은 실패가 아니라 빈 구간 결과로 처리한다.

**제외 책임**: 내용 요약, 주제 분류, 사용자 요청 검색, 영상 편집.

### 담당 3 — 영상 내용 분석

**수정 위치**: `src/video_assistant/analysis/llm.py` 및 내부 보조 파일; `tests/contract/test_analyzer.py`, 관련 단위 테스트.

**구현 클래스·계약**: `LLMContentAnalyzer(ContentAnalyzer)` / `analyze(self, transcript: Transcript) -> VideoAnalysis` / `VERSION` 필수.

**수행 작업**: 자막 전체 요약, 주제·소주제 구간 분류, 긴 자막 분할 처리, LLM 응답 구조화·검증, 실패/빈 자막 처리.

**검증**: `VideoAnalysis.video_id == transcript.video_id`, `transcript_id == transcript.id`, `analyzer_version == VERSION`; `TopicSection.segment_ids`가 실제 자막 세그먼트를 참조해야 한다. 사용자 검색어와 무관한 **재사용 가능한 분석 결과**를 생성한다.

**제외 책임**: 사용자 요청 기반 구간 선정, 계획 승인 및 렌더링.

### 담당 4 — 자연어 검색 및 구간 추천

**수정 위치**: `src/video_assistant/recommendation/llm.py` 및 내부 보조 파일; `tests/contract/test_recommender.py`, 관련 단위 테스트.

**구현 클래스·계약**: `LLMSegmentRecommender(SegmentRecommender)` / `recommend(self, request: SearchRequest, transcript: Transcript, analysis: VideoAnalysis) -> RecommendationResult` / `VERSION` 필수.

**수행 작업**: 자연어 요청 해석, 관련 자막/주제 검색, 추천 구간의 시간·순서 제안, 중복 후보 처리, 추천 이유 생성, 요청과 관련 없는 경우 빈 추천 결과 반환.

**검증**: 결과의 `request_id`, `video_id`, `transcript_id`, `analysis_id`가 입력과 일치해야 한다. `len(clips) <= request.max_clips`, 각 클립 시간은 영상 길이 내에 있으며 참조한 자막 ID가 실제로 존재해야 한다. `clips` 배열 순서가 제안 순서다.

**제외 책임**: 사용자가 수정한 계획의 버전 관리·승인, FFmpeg 실행.

### 담당 5 — 실제 영상 편집

**수정 위치**: `src/video_assistant/editing/ffmpeg.py` 및 내부 보조 파일; `tests/integration/test_ffmpeg_render.py`, 관련 단위 테스트.

**구현 클래스·계약**: `FFmpegVideoEditor(VideoEditor)` / `render(self, video: VideoAsset, plan: ApprovedEditPlan, output_path: Path) -> RenderResult` / `VERSION` 필수.

**수행 작업**: 승인된 클립을 순서대로 추출·병합, H.264 MP4 및 오디오가 있으면 AAC 인코딩, 무음 원본 대응, FFprobe로 출력 영상 확인, 실패 시 임시 파일 정리.

**검증**: 실제로 편집 계획을 적용해야 한다. `RenderResult`에는 올바른 `video_id`, `plan_id`, `plan_version`, `output_path`, `renderer_version` 및 FFprobe와 일치하는 `duration_ms`를 넣는다. 원본 영상을 단순 복사하는 기존 `StubVideoEditor`와 다르게 동작해야 한다.

**보안 규칙**: FFmpeg는 `subprocess`의 **인자 배열**을 사용하여 `shell=False`로 실행한다. 사용자 문자열을 셸 명령으로 실행하지 않고 출력 경로와 임시 파일을 제한한다.

## 5. 팀장 — 공통 계약 관리 및 통합 검토

### 5.1 팀장이 관리할 영역

| 위치 | 팀장 역할 |
|---|---|
| `core/models.py` | 필드/검증 규칙 변경의 영향 검토 및 팀 합의 |
| `core/interfaces.py` | 메서드 시그니처 변경 조율·호환성 확인 |
| `core/errors.py` | 새 오류 코드와 예외 처리 규칙 검토 |
| `core/workflow.py` | 전체 단계 연결·입출력 교차 검증 및 캐시 정책 관리 |
| `core/plan_service.py` | 수정/승인 상태·버전 정책 보전 |
| `core/storage.py`, `core/jobs.py` | 영속화·작업자 문제를 공통 담당자와 관리 |
| `core/config.py`, `.env.example`, `pyproject.toml` | 백엔드 선택 값·의존성·설정 문서 검토 |
| **`bootstrap.py`** | **담당자가 등록한 구현체와 Stub/Real 선택 구조를 검토** |

`core/`의 코드가 이미 최소한 구현되어 있으므로, 팀장은 이 코드를 모든 담당자가 수정하도록 내버려 두지 않는다. 변경 제안은 허용하되 영향 범위·하위 호환성·관련 테스트를 확인한 후 통합한다.

### 5.2 독립 테스트 후 등록·통합 순서

1. 담당자는 자기 구현을 Fixture로 **직접 호출**하여 독립 테스트한다. 이 단계에서는 `bootstrap.py`를 수정하지 않는다.
2. 기능과 테스트가 준비되면 담당자가 자기 개발 브랜치에서 해당 **레지스트리에만** 실제 구현을 등록한다.
3. 담당자는 자기 구현 하나만 Real로 선택하고 나머지는 Stub으로 두어 전체 흐름 테스트한다.
4. 필요한 패키지/API 키/모델 파일은 설치·설정 가이드에 반영하되 비밀키는 저장소에 올리지 않는다.
5. **Stub 기본값은 유지**하고 구현·등록·독립/통합 테스트를 하나의 PR로 제출한다.
6. 팀장은 PR과 충돌을 검토하고 `main` 병합 후 전체 흐름을 재검증한다.

현재 스켈레톤의 등록 구문은 다음과 같다.

```python
TRANSCRIBERS = {"stub": StubTranscriber}
ANALYZERS = {"stub": StubContentAnalyzer}
RECOMMENDERS = {"stub": StubSegmentRecommender}
EDITORS = {"stub": StubVideoEditor}
```

**음성 인식 실제 구현을 등록하는 예시**(필요한 의존성을 설치한 뒤 적용):

```python
from .transcription.whisper import WhisperTranscriber

TRANSCRIBERS = {
    "stub": StubTranscriber,
    "whisper": WhisperTranscriber,
}
```

이 구문은 **`bootstrap.py`에 적용할 예시**이며, 해당 파일의 나머지 레지스트리와 `create_application()` 함수는 그대로 유지한다. `WhisperTranscriber`가 인자 없는 생성자를 제공할 때만 이 형태를 그대로 사용할 수 있다. 현재 `_make()`는 등록한 팩토리를 **인자 없이 호출**하기 때문이다.

생성자 인자가 필요한 경우에는 담당자가 자기 브랜치의 `bootstrap.py`에 팩토리 함수를 등록한다. 팀장은 PR에서 의존성과 설정을 검토한다.

```python
def build_whisper():
    from .transcription.whisper import WhisperTranscriber
    return WhisperTranscriber(model_name="base")

TRANSCRIBERS = {
    "stub": StubTranscriber,
    "whisper": build_whisper,
}
```

팩토리 내부에서 import하면 선택하지 않은 실제 구현의 선택적 패키지가 아직 설치되지 않았을 때도 Stub 모드를 유지하기 쉽다. 실제 모델 이름과 인증 설정은 담당 구현의 요구에 따라 조정한다.

나머지 등록 위치는 동일하다.

| 모듈 | 등록 레지스트리 | 예시 백엔드 값 |
|---|---|---|
| 음성 인식 | `TRANSCRIBERS` | `whisper` |
| 내용 분석 | `ANALYZERS` | `llm` |
| 검색·추천 | `RECOMMENDERS` | `llm` |
| 영상 편집 | `EDITORS` | `ffmpeg` |

### 5.3 실제 구현 선택 및 확인

`core/config.py`는 프로젝트 루트의 **`.env`를 자동으로 읽으며**, 운영체제 환경변수가 있으면 그 값을 우선한다. `.env.example`을 `.env`로 복사해서 선택값을 변경하면 된다. 자세한 내용은 [환경 설정 가이드](ENV_CONFIGURATION.md)를 참고한다.

**예: 음성 인식만 Real**

macOS/Linux:

```bash
export TRANSCRIBER_BACKEND=whisper
export ANALYZER_BACKEND=stub
export RECOMMENDER_BACKEND=stub
export EDITOR_BACKEND=stub
streamlit run src/video_assistant/ui/app.py
```

Windows PowerShell:

```powershell
$env:TRANSCRIBER_BACKEND = "whisper"
$env:ANALYZER_BACKEND = "stub"
$env:RECOMMENDER_BACKEND = "stub"
$env:EDITOR_BACKEND = "stub"
streamlit run src/video_assistant/ui/app.py
```

**주의:** 등록만 해놓고 의존성·모델·API 키를 준비하지 않았다면 실제 실행은 실패할 수 있다. 반대로 `whisper`를 설정했는데 레지스트리에 등록되지 않았다면 현재 스켈레톤은 등록 오류를 발생시키는 것이 정상이다. 기존 자막/분석을 재사용하지 않고 새로 처리해야 한다면 `VERSION` 및 캐시 저장 내역도 확인한다.

## 6. Git 브랜치, PR 및 병합 규칙

1. 최신 `main`에서 `feature/ui`, `feature/transcription`, `feature/analysis`, `feature/recommendation`, `feature/editing` 등 작업 브랜치를 만든다.
2. 담당 디렉터리에서 실제 구현과 관련 테스트를 작성한다.
3. `python -m pytest -q`를 실행해 기존 공통 테스트에 회귀가 없는지 확인한다.
4. PR 본문에 **변경 파일, 구현 기능, 설정·의존성, 테스트 결과, 공통 계약 변경 유무**를 작성한다.
5. 공통 계약 변경은 해당 값을 쓰는 UI 및 다른 모듈 담당자의 동의를 받는다.
6. GitHub PR의 merge로 변경 사항을 병합한다. **최신 파일을 통째로 덮어써서 병합하지 않는다.**
7. `main`에서 구현체 등록 PR을 별도로 병합하고 혼합 모드 통합 테스트를 수행한다.

**중요:** 서로 다른 디렉터리에서 작업하면 Git의 *텍스트 충돌*은 줄어들지만, 타입·시간 단위·설정·런타임 의존성 등의 *기능 충돌*이 사라지는 것은 아니다.

### 6.1 커밋 메시지 작성

기존 브랜치·PR·병합 규칙을 유지하며, 커밋 메시지는 `유형: 변경 내용`으로 작성한다.
제목은 변경 내용을 구체적으로 설명하며 한국어를 사용할 수 있다.

| 유형 | 사용 목적 | 예시 |
|---|---|---|
| `feat` | 실제 기능 또는 업무 API 추가 | `feat: 추천 요청 API 구현` |
| `fix` | 잘못된 동작 수정 | `fix: 추천 구간 시간 범위 검증 수정` |
| `refactor` | 동작 변경 없는 코드 구조 개선 | `refactor: 추천 후보 정렬 함수 분리` |
| `test` | 테스트만 추가·수정 | `test: 무음 영상 자막 테스트 추가` |
| `docs` | 문서 추가·수정 | `docs: API 실행 방법 추가` |
| `chore` | 개발 환경·패키지·설정 정리 | `chore: API 기본 세팅 추가` |
| `style` | 동작 변경 없는 코드 포맷 정리 | `style: import 순서 정리` |

- 하나의 커밋은 하나의 변경 목적을 중심으로 작성한다. 기능과 관련 테스트를 함께 포함해도 된다.
- 제목만으로 부족하면 본문에 변경 이유와 영향 범위를 적는다.
- 관련 Issue가 있으면 본문에 `Refs #이슈번호`로 연결한다.
- `.env`, API 키, 가상환경, runtime 및 캐시 파일은 커밋하지 않는다.

### 6.2 Issue 작성

Issue는 앞으로 수행할 작업과 완료 조건을 기록하는 용도다.
기존 기능별 브랜치 이름(`feature/analysis`, `feature/recommendation` 등)은 그대로 사용한다.

- 제목은 작업 내용을 구체적으로 작성한다. 예: `추천 요청·조회 API 구현`.
- 담당자, 작업 목적, 구현 범위, 완료 조건, 선행 작업을 적는다.
- 기능 구현과 API 연결이 큰 작업이면 Issue를 분리할 수 있다.
- 서로 연결되는 작은 API는 하나의 Issue로 묶어도 된다. API 개수와 Issue 개수를 반드시 맞출 필요는 없다.
- 공통 계약 변경이 필요하면 영향받는 담당자와 협의할 내용을 적는다.
- 버그 Issue에는 재현 방법, 기대 결과, 실제 결과, 실행 환경을 적는다.

**Issue 본문 예시**

```markdown
## 작업 목적
사용자의 자연어 요청으로 추천 작업을 시작하고 결과를 조회한다.

## 작업 내용
- [ ] 프론트와 요청·응답 형식 합의
- [ ] 기존 ApplicationService에 추천 요청 API 연결
- [ ] 추천 결과 조회 API 구현
- [ ] API 테스트 작성

## 완료 조건
- [ ] 정상 요청 시 작업 ID를 반환한다.
- [ ] 완료된 추천 결과를 조회할 수 있다.
- [ ] 잘못된 입력·없는 결과에 대한 응답을 확인한다.

## 선행 작업·협의 사항
추천 기능 구현 Issue #번호

## 담당자
GitHub 담당자 지정
```

### 6.3 PR 작성

PR은 작업 브랜치의 변경 사항을 검토받고 main에 병합하기 위한 요청이다.
기존 규칙대로 본문에 **변경 파일, 구현 기능, 설정·의존성, 테스트 결과, 공통 계약 변경 유무**를 적는다.

- 제목은 커밋과 같은 `유형: 변경 내용` 형식을 사용한다.
- 관련 Issue를 `Refs #이슈번호`로 연결한다. Issue의 완료 조건을 모두 해결한 PR은 `Closes #이슈번호`를 사용할 수 있다.
- 실제 실행한 테스트와 결과를 적고, 실패하거나 실행하지 못한 항목은 이유를 함께 적는다.
- 공통 계약 변경이 있으면 영향받는 담당자와 합의한 내용을 적는다.
- 기존 팀장 검토·GitHub PR 병합 절차를 유지한다. 필수 승인 수나 특정 병합 방식은 이 보충 안내에서 새로 지정하지 않는다.

**PR 본문 예시**

```markdown
## 관련 Issue
Refs #번호

## 구현 기능
- 추천 요청·조회 API 연결

## 변경 파일
- src/video_assistant/api/routes/recommendations.py
- tests/api/test_recommendations.py

## 설정·의존성
- 추가 없음 / 필요한 설정 및 패키지 기재

## 테스트 결과
- 실행 명령:
- 통과·실패·미실행 결과와 이유:

## 공통 계약 변경
- 없음 / 변경 내용과 관련 담당자 협의 내용 기재
```

### 6.4 작업 순서 예시

1. `추천 요청·조회 API 구현` Issue를 작성하고 담당자를 지정한다.
2. 최신 main을 기준으로 기존 이름 규칙에 맞는 `feature/recommendation` 브랜치를 만든다.
3. 기능 코드와 API, 관련 테스트를 담당 영역에서 작성한다. 필요 시 Issue에서 작업을 나눈다.
4. `feat: 추천 요청·조회 API 구현`처럼 변경 목적이 드러나는 메시지로 커밋한다.
5. 작업 브랜치를 GitHub에 올리고 관련 Issue를 연결한 PR을 작성한다.
6. 기존 규칙에 따라 팀장·관련 담당자의 검토 후 main에 병합하고 통합 동작을 확인한다.

## 7. 실행 및 테스트

최초 환경 준비:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
ffprobe -version
```

공통 동작 테스트:

```bash
python scripts/smoke_test.py
python -m pytest -q
```

UI 실행:

```bash
streamlit run src/video_assistant/ui/app.py
```

`examples/demo.mp4`로 업로드 → 준비 → 추천 → 계획 수정·승인 → 렌더링의 흐름을 확인한다. **현재 Stub 자막/추천은 영상의 실제 내용과 관계없고, Stub 편집은 원본 파일을 복사할 뿐 컷 편집을 수행하지 않는다.** 실제 품질 검증은 해당 담당자의 Real 구현으로 교체한 뒤 수행한다.

팀원 PR마다 최소한 다음 사례를 점검한다.

| 담당 | 정상 사례 | 예외·경계 사례 |
|---|---|---|
| UI | 전체 화면 흐름 진행 | 빈 추천, 작업 실패, 승인 충돌 |
| 음성 인식 | 실제 자막 생성 | 무음, 인식 실패, 시간 범위 초과 |
| 내용 분석 | 요약·주제 생성 | 빈 자막, LLM 형식 오류, 잘못된 자막 참조 |
| 검색·추천 | 관련 구간 추천 | 추천 없음, 최대 개수 초과, 잘못된 시간/ID |
| 영상 편집 | 실제 구간 추출·병합 | 승인 전 입력, 오디오 없는 영상, 출력 검증 실패 |
| 공통/팀장 | Stub/Real 혼합 실행 | 재실행 중 캐시, 계획 충돌, 작업 실패 복구 |

## 8. 완료 판단 기준

**개별 담당자 완료:** 공개 ABC를 구현하고, `VERSION`·오류 처리·단위/계약 테스트를 갖춘 PR이 승인된 상태.

**담당자 통합 검증 완료:** 자기 브랜치에서 `bootstrap.py` 등록 후 다른 Stub과 혼합 실행이 성공하고 PR을 제출한 상태.

**팀장 통합 완료:** 해당 PR을 검토·병합하고 `main`에서 회귀 테스트가 통과한 상태.

**프로젝트 완료:** 다섯 기능을 실제 구현으로 선택하여, **실제 영상의 내용에 기초한** 자막 → 분석 → 구간 추천 → 사용자 수정·승인 → **계획대로 컷 편집한 MP4** 출력과 다운로드를 전체 테스트로 확인한 상태.

> 이 매뉴얼은 **기초 협업 규칙의 초안**이다. 모델/인터페이스의 변경이나 기능 추가는 팀장과 영향받는 담당자가 검토해 버전을 올려 반영한다.
