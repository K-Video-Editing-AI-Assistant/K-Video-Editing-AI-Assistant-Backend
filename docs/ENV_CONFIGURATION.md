# 환경 설정 — `.env`로 실행 모드 선택

[← 설치·실행](SETUP_AND_RUN.md) · [← 처음 시작하기](START_HERE.md)

## 1. 최초 한 번만: `.env` 만들기

프로젝트 루트(`pyproject.toml`과 `.env.example`이 있는 폴더)에서 실행합니다.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
cp .env.example .env
```

`.env.example`은 팀 공통 예시 파일입니다. **프로그램이 자동으로 읽는 파일은 `.env`**입니다.

## 2. 내 담당 모듈 선택하기

`.env`를 메모장 또는 VS Code로 열어 수정합니다.

```dotenv
VIDEO_ASSISTANT_RUNTIME_DIR=runtime
MAX_UPLOAD_MB=200
TRANSCRIBER_BACKEND=stub
ANALYZER_BACKEND=stub
RECOMMENDER_BACKEND=keyword
EDITOR_BACKEND=stub
```

위 예시는 **추천만 `keyword`**, 나머지는 Stub입니다. `RECOMMENDER_BACKEND=llm`은 `bootstrap.py`에 `llm` 구현체가 등록되고 필요한 패키지/API 키가 준비된 뒤 사용하세요.

현재 스켈레톤에 등록된 선택지:

| 변수 | 지금 선택 가능한 값 | 담당 구현이 완성된 후 추가 예시 |
|---|---|---|
| `TRANSCRIBER_BACKEND` | `stub` | `whisper` |
| `ANALYZER_BACKEND` | `stub`, `simple` | `llm` |
| `RECOMMENDER_BACKEND` | `stub`, `keyword` | `llm` |
| `EDITOR_BACKEND` | `stub` | `ffmpeg` |

개별 담당자는 독립 테스트할 때 해당 클래스를 직접 호출하므로 `.env`나 `bootstrap.py`를 바꿀 필요가 없습니다. **모듈 구현이 준비되어 전체 흐름 테스트를 시작할 때** `bootstrap.py`에 등록하고 `.env`로 선택합니다.

## 3. 실행

프로젝트 루트에서 가상환경을 활성화하고 실행합니다.

```powershell
python -m streamlit run src/video_assistant/ui/app.py
```

`Settings.from_env()`가 프로젝트 루트 `.env`를 읽습니다. 파일의 값과 충돌하는 운영체제 환경변수가 있다면 **운영체제 환경변수가 우선**하며, 두 곳 모두 없다면 기본값인 `stub`이 적용됩니다.

설정을 변경했으면 Streamlit을 종료(`Ctrl+C`)하고 재실행하세요. 서비스 인스턴스가 캐시되고 `.env`가 처음 실행할 때 읽히므로 핫 리로드를 기대하면 안 됩니다.

## 4. 자주 헷갈리는 상황

| 상황 | 해결 |
|---|---|
| `.env.example`만 수정했다 | `.env` 파일로 복사한 뒤 `.env`를 수정하세요 |
| `$env:RECOMMENDER_BACKEND`를 이전에 설정했다 | PowerShell에서 `Remove-Item Env:RECOMMENDER_BACKEND`로 해제하거나 새 터미널을 열고 실행하세요 |
| `.env`를 바꿨는데 예전 모듈이 실행된다 | Streamlit 종료 후 새로 시작하고 운영체제 환경변수 우선순위를 확인하세요 |
| `llm`으로 설정했더니 미등록 오류가 난다 | 실제 구현체 클래스를 완성하고 `bootstrap.py` 레지스트리에 추가해야 합니다 |
| Python 패키지를 못 찾는다 | 가상환경에서 `python -m pip install -e ".[test]"`를 다시 실행하세요 |

### API 키 및 보안

실제 LLM 구현이 필요로 하는 키는 개인 `.env`에만 입력하세요(예: `OPENAI_API_KEY=...`). `Settings.from_env()`가 `.env` 값을 프로세스 환경변수로 로딩하므로, 구현체에서도 `os.getenv("OPENAI_API_KEY")`로 읽을 수 있습니다.

- `.env`는 이미 `.gitignore`에 등록되어 있으므로 Git에 추가하지 마세요. `.env.example`에는 실제 비밀키를 절대 기록하지 않습니다.
- `.env` 값은 현재 앱 프로세스에서 사용할 설정입니다. 개인 API 키를 다른 사용자에게 공유하지 마세요.
- 운영체제 환경변수는 `.env`보다 우선합니다. 임시 테스트용으로 `$env:`를 사용했으면 설정이 남아 있는지 확인하세요.

### 참고 — `.env` 로딩과 명시적 테스트 설정의 차이

- `Settings.from_env()` 또는 인자 없는 `create_application()`은 `.env`를 자동으로 읽습니다.
- `Settings(runtime_dir=..., recommender_backend="stub")`을 직접 생성해 `create_application(settings)`에 전달하는 테스트는 `.env`에 의존하지 않습니다.
- `scripts/smoke_test.py`처럼 명시적인 `Settings(...)`를 사용하는 테스트는 `.env` 변경과 무관하게 지정한 백엔드로 실행됩니다.
