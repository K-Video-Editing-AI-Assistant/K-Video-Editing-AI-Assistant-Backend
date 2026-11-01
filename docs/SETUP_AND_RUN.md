# 설치·실행·테스트 안내

이 문서는 **처음 로컬 환경을 구성하는 사람**을 위한 실행 명령만 담습니다. 작업 내용은 [시작 가이드](START_HERE.md)에 있습니다.

## 준비물

- Python 3.11 이상
- FFmpeg 설치 (`ffprobe -version` 명령으로 확인)
- 프로젝트 폴더 (`pyproject.toml` 파일이 보여야 함)

> `pip install`은 Python 패키지를 설치하지만 **FFmpeg·FFprobe 실행 파일은 설치하지 않습니다.** OS에 맞게 별도로 설치하고 `PATH`를 등록하세요.

## Windows PowerShell

프로젝트 루트에서 한 번 실행:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
ffprobe -version
```

매번 실행할 때는 새 PowerShell 터미널에서 가상환경을 활성화한 후:

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run src/video_assistant/ui/app.py
```

## macOS / Linux

프로젝트 루트에서 한 번 실행:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
cp .env.example .env
ffprobe -version
```

이후:

```bash
source .venv/bin/activate
python -m streamlit run src/video_assistant/ui/app.py
```

## 앱에서 실행해 볼 순서

1. `examples/demo.mp4` 업로드 → **영상 등록**
2. **영상 준비 작업 시작** → Stub 자막과 Stub 분석 확인
3. 검색어 `AI 활용` 입력 → **구간 추천 요청**
4. 추천 결과로 **편집 계획 생성 → 수정/승인**
5. **영상 결과 생성** → 테스트용 결과 재생/다운로드

**현재 편집 Stub은 승인한 부분을 잘라내지 않고 원본을 복사**합니다. 실제 편집 동작 확인은 `FFmpegVideoEditor` 구현 이후에 합니다.

## 자동 테스트

```bash
python scripts/show_contract_chain.py
python scripts/smoke_test.py
python -m pytest -q
```

계약만 확인하려면:

```bash
python -m pytest -q tests/contract/test_module_io_contracts.py
```

## `.env` 파일로 백엔드 선택 (권장)

`.env.example`은 예시 파일이며 직접 읽지 않습니다. 위 명령으로 만든 **프로젝트 루트의 `.env`** 파일을 편집하세요.

```dotenv
VIDEO_ASSISTANT_RUNTIME_DIR=runtime
MAX_UPLOAD_MB=200
TRANSCRIBER_BACKEND=stub
ANALYZER_BACKEND=simple
RECOMMENDER_BACKEND=keyword
EDITOR_BACKEND=stub
```

해당 예시는 지금 등록된 분석(`simple`)과 추천(`keyword`) 구현을 사용합니다. 기본값대로 전부 `stub`을 쓰고 싶다면 `.env.example`을 복사한 뒤 값을 변경하지 마세요.

파일을 저장한 뒤 별도 `$env:` 설정 없이 다음 명령만 입력합니다.

```powershell
python -m streamlit run src/video_assistant/ui/app.py
```

**우선순위:** 현재 터미널의 환경변수 > `.env` > 기본값(`stub`). 이전에 `$env:RECOMMENDER_BACKEND = "llm"`을 설정했다면 `.env`의 `stub` 값보다 우선하므로, 원한다면 `Remove-Item Env:RECOMMENDER_BACKEND`로 해당 변수를 해제하거나 새 터미널을 여세요.

설정 파일을 바꾼 뒤에는 실행 중인 Streamlit을 종료(`Ctrl+C`)하고 다시 실행하세요. `whisper`, `llm`, `ffmpeg`는 **실제 구현체를 `bootstrap.py`에 등록한 뒤에만** 선택할 수 있습니다. API 키를 `.env`에 넣을 수 있지만 **`.env`를 Git에 올리지 마세요.** 상세 내용은 [환경 설정 가이드](ENV_CONFIGURATION.md)를 참고하세요.

## 일회성으로 백엔드를 바꿔보려면 (Windows PowerShell 예시)

```powershell
$env:TRANSCRIBER_BACKEND = "stub"
$env:ANALYZER_BACKEND = "simple"
$env:RECOMMENDER_BACKEND = "keyword"
$env:EDITOR_BACKEND = "stub"
python -m streamlit run src/video_assistant/ui/app.py
```

`simple` 분석·`keyword` 추천은 연습용 예제입니다. **실제 LLM/Whisper/FFmpeg 편집 백엔드는 아직 등록되지 않았습니다.** 변경 후 Streamlit을 재시작하세요. 이 PowerShell 변수는 `.env` 값보다 우선합니다.

## 자주 막히는 부분

| 현상 | 우선 확인할 것 |
|---|---|
| `ModuleNotFoundError: video_assistant` | 프로젝트 루트에서 `python -m pip install -e ".[test]"` 실행 여부 |
| `streamlit`을 찾을 수 없음 | `.venv` 활성화 여부, `python -m streamlit`으로 실행 |
| `ffprobe`가 인식되지 않음 | FFmpeg 별도 설치 및 `PATH` 설정 |
| PowerShell에서 활성화 스크립트 차단 | 활성화 대신 `.\.venv\Scripts\python.exe` 경로로 직접 실행 가능 (아래 참고) |
| `llm` 또는 `whisper` 미등록 오류 | 해당 구현체가 준비되었는지, 내 브랜치의 `bootstrap.py`에 등록했는지 확인 (독립 테스트에는 등록 불필요) |
| 이전 설정이 적용된 것 같음 | Streamlit 재시작, `$env:`가 `.env`를 덮어쓰는지 확인; 필요하면 `Remove-Item Env:RECOMMENDER_BACKEND` |

PowerShell 활성화 없이 설치·실행하는 대체 예:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m streamlit run src/video_assistant/ui/app.py
```

다음으로 할 일: [내 담당 작업 선택](ROLE_IMPLEMENTATION_MANUAL.md).
