# AI 영상편집 어시스턴트

> **현재 개발 방향: React 프론트엔드 + FastAPI 백엔드.** 아래 Streamlit 직접 호출 설명은 기존 테스트용 구조입니다.

> **별도 HTTP 서버(FastAPI 등)를 사용하지 않습니다.** Streamlit 화면에서 같은 Python 프로세스의 `ApplicationService`를 직접 호출합니다. 이 서비스 계층을 맡는 팀원의 공식 역할명은 **Application 담당**입니다.

> 실제 Whisper·LLM 분석은 아직 미구현이며, 기본 동작은 **Stub(테스트용 결과)** 입니다. 화면은 개발 검증용 최소 UI입니다.

## 문서 바로가기

| 원하는 작업                       | 확인할 문서                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------- |
| 처음 설치·실행하기                | **이 README의 [빠른 시작](#1-빠른-시작)** 또는 [START_HERE](docs/START_HERE.md)          |
| 현재 시스템 구조 이해             | [아키텍처](docs/ARCHITECTURE.md)                                                         |
| 내가 구현해야 할 파일과 기능 확인 | [5인 담당자별 작업 가이드](docs/ROLE_GUIDE.md)                                           |
| 모델 필드와 Output 형식 이해      | [Input/Output 계약서](docs/INPUT_OUTPUT_CONTRACT.md) → [`models.py`](src/core/models.py) |
| 독립 테스트 / 구현체 등록 / PR    | [개발·테스트 가이드](docs/DEVELOPMENT_TESTING.md)                                        |
| 기존 프로젝트와 무엇이 달라졌는지 | [이관 가이드](docs/MIGRATION.md)                                                         |

## 1. 빠른 시작

### 먼저 필요한 것

- **Python 3.11 이상**
- **FFmpeg + FFprobe**: 시스템에 별도로 설치하고 실행 파일을 PATH에 등록해야 합니다. `pip install`만으로 설치되지 않습니다.
- Windows PowerShell, macOS Terminal 또는 Linux 터미널

Windows PowerShell에서 **프로젝트 루트**(`pyproject.toml`이 있는 폴더)를 열고:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
ffmpeg -version
ffprobe -version
```

macOS / Linux라면 가상환경 활성화와 `.env` 복사만 달라집니다:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
cp .env.example .env
ffmpeg -version
ffprobe -version
```

**정상 설치·실행 확인:**

```powershell
python -m pytest -q
python scripts/smoke_test.py
python -m streamlit run src/ui/app.py
```

Streamlit 기본 주소는 `http://localhost:8501`입니다. **터미널 하나**에서 실행합니다. 화면 실행 중인 동안 같은 터미널은 사용 중이므로 테스트 명령은 새 터미널에서 실행할 수 있습니다.

### 화면에서 따라 할 흐름

1. **새 프로젝트 만들기** → `examples/demo.mp4`를 등록합니다. 같은 파일을 다른 이름으로 준비해 여러 영상 등록도 가능합니다.
2. **영상 준비 시작** → Whisper Stub의 자막, AI Stub의 주제·키워드 생성.
3. **자연어 추천 요청** → AI Stub이 다중 영상 클립을 제안.
4. **편집 초안 만들기** → 필요하면 구간의 시간·순서를 수정하고 승인.
5. **렌더링** → 개발용 Stub이 첫 번째 원본 MP4를 복사해 저장. 화면에서 재생·다운로드 가능.

> **주의:** Stub 결과는 실제 영상을 분석하거나 승인된 클립으로 자른 결과가 아닙니다. `EDITOR_BACKEND=ffmpeg`를 선택하면 기본적인 실제 컷 편집을 실행할 수 있지만 **자막 영상 합성·고급 스타일·전환 효과는 아직 구현하지 않았습니다**.

## 2. 이번 통합본에서 실제로 동작하는 부분

| 영역                                         | 현 상태                                                    |
| -------------------------------------------- | ---------------------------------------------------------- |
| 공통 Pydantic 모델·ABC 인터페이스·오류       | 구현·검증 가능                                             |
| 여러 원본 영상 프로젝트 등록 및 FFprobe 검증 | 구현                                                       |
| Whisper 자막 인터페이스 / 실제 음성 인식     | **Stub 구현 / 실제 Whisper 미구현**                        |
| AI 전처리·내용 분석·키워드·추천              | **Stub 구현 / 실제 LLM 미구현**                            |
| 자동 파일 저장                               | 원본 MP4, 자막 JSON/SRT, 분석 JSON, 추천·계획·출력         |
| 편집 계획 생성·수정·승인·버전 검증           | 구현                                                       |
| 영상 출력                                    | Stub은 원본 복사 / `ffmpeg` 선택 시 실제 다중 영상 컷 편집 |
| 장시간 작업                                  | 한 프로세스의 내부 작업자, JSON 상태 저장                  |
| Streamlit UI                                 | 기본 기능 연결 검증용 화면                                 |
| 최종 UI 시안 및 고급 편집 기능               | **미구현(향후 담당자 작업)**                               |

이 프로젝트는 팀원들이 바로 구현을 시작할 수 있는 **통합 개발 출발점**이지 완성된 AI 서비스가 아닙니다.

## 3. 프로젝트 폴더 구조

```text
AI 영상편집 어시스턴트/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── src/
│   ├── bootstrap.py           # Stub/실제 구현체 등록 및 연결
│   ├── core/                  # PM: 공통 모델·인터페이스·오류
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── interfaces.py
│   │   └── errors.py
│   ├── application/           # Application: 서비스·계획·저장·작업자
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── service.py
│   │   ├── plans.py
│   │   ├── storage.py
│   │   └── jobs.py
│   ├── ui/                    # UI: Streamlit
│   │   ├── __init__.py
│   │   └── app.py
│   ├── ai/                    # AI 영상분석: 전처리·요약·추천
│   │   ├── __init__.py
│   │   ├── stub.py
│   │   ├── preprocessing.py
│   │   ├── analyzer.py
│   │   └── recommender.py
│   └── processing/            # 영상처리: 업로드·Whisper·FFmpeg
│       ├── __init__.py
│       ├── files.py
│       ├── stub.py
│       ├── whisper.py
│       └── ffmpeg.py
├── docs/                      # 설계·계약·담당자 개발 가이드
├── tests/                     # 계약·통합 테스트와 Fixture
├── scripts/
│   ├── smoke_test.py
│   └── show_contract_chain.py
├── examples/demo.mp4          # 테스트용 영상
└── runtime/                   # 실행 시 자동 생성 (Git 제외)
```

소스 코드는 `src/` 바로 아래의 `core`, `application`, `ui`, `ai`, `processing` 패키지로 구성합니다. `bootstrap.py`는 `src/` 최상위 모듈입니다. 서비스 이름은 **AI 영상편집 어시스턴트**입니다. 기존 `video_assistant.*` Import는 더 이상 사용하지 않습니다.

### Import 변경 안내

```python
from core.models import Transcript
from application.service import ApplicationService
from bootstrap import create_application
```

- `src/`의 각 폴더에는 `__init__.py`가 있어 일반 Python 패키지로 취급됩니다.
- `pip install -e ".[test]"`로 `src/`를 Python 모듈 탐색 경로에 등록합니다. `pyproject.toml`에서 다섯 패키지와 최상위 `bootstrap` 모듈을 함께 패키징합니다.
- `core`, `ai` 같은 이름은 일반적이므로, 향후 별도 라이브러리로 배포할 때는 패키지 이름 충돌 가능성을 재검토해야 합니다.
- `application/config.py`는 위치 변경 후에도 프로젝트 루트의 `.env`를 자동으로 읽습니다.

## 4. 실제 데이터가 이동하는 순서

```text
[Streamlit UI]
     |
     v
[ApplicationService] -- 프로젝트 등록/저장
     |
     |-- (영상처리) VideoAsset -> Transcriber -> Transcript
     |-- (AI)       Transcript -> ProcessedTranscript
     |-- (AI)       ProcessedTranscript -> VideoAnalysis
     |-- (AI)       Project + VideoAnalysis 목록 -> ProjectAnalysis/키워드
     |
     |-- (AI)       SearchRequest + 위 결과 -> RecommendationResult
     |-- (Application) RecommendationResult -> EditPlan -> ApprovedEditPlan
     `-- (영상처리) 영상 목록 + 승인 계획 -> RenderResult / MP4
     |
     v
[Streamlit UI에서 결과 표시/다운로드]
```

각 담당자의 클래스는 [`core/interfaces.py`](src/core/interfaces.py)에 선언된 함수를 구현하고, [`core/models.py`](src/core/models.py)의 **정확한 Pydantic 객체**를 반환해야 합니다. 다음 기능을 호출하고 결과를 저장·검증하는 작업은 `ApplicationService`가 담당합니다.

**재사용:** 사용자 요청만 달라지면 이전 `Transcript`와 `VideoAnalysis`를 재사용해 추천만 다시 실행합니다. 새 원본 영상을 등록하면 기존 프로젝트 단위 분석·추천·현재 계획을 무효화합니다.

## 5. `.env`로 실행 모드 선택

`.env.example`은 **설정 예시 파일**일 뿐입니다. 복사한 `.env`가 실제 실행 설정입니다.

```dotenv
RUNTIME_DIR=runtime
TRANSCRIBER_BACKEND=stub
PREPROCESSOR_BACKEND=stub
ANALYZER_BACKEND=stub
PROJECT_ANALYZER_BACKEND=stub
RECOMMENDER_BACKEND=stub
EDITOR_BACKEND=stub
```

- 모든 구현의 기본값은 `stub`입니다.
- `EDITOR_BACKEND=ffmpeg`는 **이미 등록된 실제 FFmpeg 컷 편집**을 사용합니다.
- Whisper/LLM은 코드 완성 후 [`bootstrap.py`](src/bootstrap.py)에 등록해야 설정에서 선택할 수 있습니다. 미구현 클래스를 선택해도 자동으로 작동하지 않습니다.
- 우선순위: **PowerShell 등 운영체제 환경변수 > `.env` > 기본값**.
- `.env` 설정 변경 후 Streamlit을 종료하고 다시 실행하세요(`st.cache_resource` 사용).
- 외부 LLM 서비스의 **API 키**는 개인 `.env`에 보관하고 Git에 올리지 않습니다. 여기서 API 키는 외부 서비스 인증 정보이며 팀 내 담당자 명칭과는 무관합니다.

## 6. 담당자별 첫 번째 작업

**공식 역할 명칭:** PM / UI(프론트) / AI 영상분석 / 영상처리 / **Application 담당**.

Application 담당은 `application/`의 Python 서비스·워크플로·계획·저장·작업 관리를 맡으며, 별도 HTTP 서버를 구축하지 않습니다.

| 담당                 | 어디부터 볼까?                                                         | 가장 먼저 할 일                                           |
| -------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------- |
| **PM**               | [`core/`](src/core/models.py), [계약서](docs/INPUT_OUTPUT_CONTRACT.md) | 역할별 데이터 필드·ID·시간·승인 규칙 검토                 |
| **UI**               | [`ui/app.py`](src/ui/app.py)                                           | 서비스 메서드를 호출하는 기본 화면 실행 확인              |
| **AI 영상분석**      | [`ai/stub.py`](src/ai/stub.py), [`ai/`](src/ai/analyzer.py)            | 공통 Fixture로 `preprocess/analyze/recommend` 독립 테스트 |
| **영상처리**         | [`processing/`](src/processing/whisper.py)                             | MP4 메타데이터·Whisper 출력·FFmpeg 편집 독립 테스트       |
| **Application 담당** | [`application/service.py`](src/application/service.py)                 | Stub으로 전체 실행 순서·결과 저장·계획 승인 검증          |

**협업 원칙:** 각자 독립 개발 → Fixture/Stub 독립 테스트 → 완성 후 자기 브랜치에서 구현체 등록 → 전체 흐름 테스트 → PR 제출. 팀장이 등록할 때까지 기다릴 필요가 없습니다. [자세한 설명](docs/ROLE_GUIDE.md)

## 7. 로컬 생성 데이터

실행 중 `runtime/projects/<project_id>/`에 MP4·JSON·SRT가 저장됩니다. 전체 예시는 [아키텍처 문서](docs/ARCHITECTURE.md)의 저장 구조를 참조하세요. `.venv/`, `.env`, `runtime/`은 Git에 포함하지 않습니다.

## 8. 운영상 제한

- MVP는 한 Streamlit 프로세스·내부 작업자 1개·로컬 JSON 저장 기준입니다.
- 로그인/다중 사용자 권한 관리, 작업 자동 복구, 다중 서버, 클라우드 저장은 없습니다.
- `ProjectAnalysis`의 프로젝트 키워드는 준비 작업 재실행 시 생성되며, 영상별 자막·분석은 구현 버전과 원본 참조가 동일하면 재사용합니다.
- 실제 LLM·Whisper는 명시적인 미구현 클래스입니다. 실제 모델을 연결하기 전에 팀원별 계약·테스트를 먼저 완료하세요.
- 실제 FFmpeg는 컷 편집과 MP4 출력의 **기초 구현**이며 자막 스타일은 계획에 저장되지만 아직 영상에 합성되지 않습니다.
- 이전 단일 영상 프로젝트의 구현과 직접 호환되지 않는 모델이 있습니다. [이관 가이드](docs/MIGRATION.md)를 확인하고 별도 브랜치에서 적용하세요.
