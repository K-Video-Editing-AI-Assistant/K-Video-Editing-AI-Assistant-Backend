# VideoAssistant — 팀 개발용 초기 프로젝트

이 배포본은 **업로드한 프로젝트를 기준으로 정리한 깨끗한 개발 시작 버전**입니다. 5명의 담당자가 공통 계약을 유지하면서 **독립 개발 → 단위/계약 테스트 → Stub과 통합 테스트 → PR** 순서로 작업하도록 준비했습니다.

> **현재 구현 상태:** Streamlit 화면, Pydantic 계약, 워크플로·저장·작업 큐, 네 기능의 Stub, 키워드 추천/규칙 기반 분석 예제가 있습니다. **실제 Whisper 음성 인식·LLM 분석/추천·FFmpeg 컷 편집은 아직 구현하지 않았습니다.** Stub 편집기는 원본 MP4를 복사할 뿐 구간을 자르지 않습니다.

## 1. 최초 설치 (Windows PowerShell)

Python 3.11 이상과 FFmpeg/FFprobe가 준비되어 있어야 합니다. 프로젝트 루트(`pyproject.toml`이 있는 폴더)에서 실행하세요.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
ffprobe -version
python -m pytest -q
```

- `.env.example`은 팀 공통 예시이고 `.env`는 본인 설정입니다. 기본값은 전부 `stub`입니다.
- **`dotenv` 모듈 오류가 발생하면** 활성화한 가상환경에서 `python -m pip install -e ".[test]"`를 다시 실행하세요. `pyproject.toml`에 `python-dotenv`가 포함되어 있습니다.
- FFmpeg와 FFprobe는 `pip`에서 설치하지 않습니다. OS에 맞게 별도 설치하고 PATH에 추가하세요.
- macOS/Linux 및 PowerShell 실행 오류 대응: [설치 안내](docs/SETUP_AND_RUN.md)

## 2. 앱 실행

```powershell
python -m streamlit run src/video_assistant/ui/app.py
```

1. `examples/demo.mp4`를 업로드하고 영상을 등록합니다.
2. **영상 준비**에서 Stub 자막·분석 결과를 생성합니다.
3. `AI 활용`으로 추천을 요청합니다.
4. 편집 계획을 생성·승인하고 결과 MP4를 생성합니다.

이는 **연결 확인용 데모**입니다. 실제 음성/내용 또는 편집 품질을 보여주는 것은 아닙니다.

## 3. 각 담당자의 시작점

| 역할 | 담당 파일 | 가이드 |
|---|---|---|
| UI | `src/video_assistant/ui/` | [UI](docs/roles/ui.md) |
| 음성 인식 | `src/video_assistant/transcription/whisper.py` | [음성 인식](docs/roles/transcription.md) |
| 내용 분석 | `src/video_assistant/analysis/llm.py` | [내용 분석](docs/roles/analysis.md) |
| 검색·추천 | `src/video_assistant/recommendation/llm.py` | [검색·추천](docs/roles/recommendation.md) |
| 영상 편집 | `src/video_assistant/editing/ffmpeg.py` | [영상 편집](docs/roles/editing.md) |
| 팀장 | `core/`, `bootstrap.py`, PR 검토 | [팀장](docs/roles/lead.md) |

**개발 순서:** [처음 시작하기](docs/START_HERE.md) → [담당자별 업무](docs/ROLE_IMPLEMENTATION_MANUAL.md) → [독립/통합 테스트 절차](docs/DEVELOPMENT_TEST_FLOW.md).

모듈 구현 중에는 **`bootstrap.py`에 등록할 필요 없이 Fixture로 내 함수만 직접 테스트**합니다. 완료 후 자기 브랜치에서 레지스트리에 추가하고 다른 모듈은 Stub으로 두어 전체 흐름을 검증합니다.

## 4. 유용한 명령

```powershell
python -m pytest -q
python scripts/show_contract_chain.py
python scripts/smoke_test.py
python -m pytest -v tests/contract/test_recommender_keyword.py
```

**문서/API 탐색:** [공통 Input/Output 계약](docs/INPUT_OUTPUT_CONTRACT_V1.md) · [실제 JSON 모델 예시](docs/CONTRACT_SAMPLE_OUTPUTS.md) · [환경 설정](docs/ENV_CONFIGURATION.md) · [세부 문서 목차](docs/REFERENCE_INDEX.md).

## 5. 배포본에서 제외한 항목

- `.venv/`, `.pytest_cache/`, `__pycache__/`, `*.egg-info/` 등 개인 환경과 생성 파일
- `.env` (개인 설정·API 키가 들어갈 수 있음) — 대신 **`.env.example`** 제공
- `runtime/` (업로드·작업·출력 결과)
- 개인 실습으로 추가된 `test_recommendation_first_step.py`와 중복 안내서 `EXAMPLE_START_HERE.md`

**주의:** 원본 업로드에 대한 정리 작업입니다. 사용자별로 작성한 실제 기능 코드가 추후 별도 브랜치에 있다면 이 ZIP으로 덮어쓰지 마세요.

팀장이 추후 동일한 방식으로 공유용 ZIP을 다시 만들려면 `python scripts/build_starter_zip.py`를 실행할 수 있습니다. 이 스크립트는 `.venv`, `.env`, 실행 결과, 캐시를 자동으로 제외합니다.

## FastAPI / Swagger (API 개발 기본 서버)

현재 `GET /health`만 제공합니다. 기능별 API는 이후 담당자가 추가합니다.
기존 Streamlit·모듈 직접 테스트와 파일·JSON 저장 방식은 유지합니다. DB는 사용하지 않습니다.

```bash
python -m pip install -e ".[test]"
python -m uvicorn video_assistant.api.app:app --reload --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs · [API 개발 안내](docs/API_DEVELOPMENT.md).
