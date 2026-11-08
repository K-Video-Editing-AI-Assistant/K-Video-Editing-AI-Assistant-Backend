# AI 영상편집 어시스턴트 시작 가이드

> 처음 참여한 팀원은 **README → 이 페이지 → 자신의 담당 페이지**만 읽고 개발을 시작하세요.

## 먼저 알아둘 3가지

- 하나의 Python 앱입니다. Streamlit은 화면, `application/`은 Python 서비스입니다. FastAPI는 없습니다.
- `core/models.py`는 데이터 형태, `core/interfaces.py`는 구현할 함수 계약입니다. 기능 알고리즘을 Core에 넣지 않습니다.
- 다른 담당자의 구현이 없어도 Stub과 공통 Fixture로 **독립 테스트부터** 할 수 있습니다.

## 첫 실행 (Windows PowerShell)

프로젝트 루트에서 다음 명령을 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
ffprobe -version
python -m pytest -q
python scripts/smoke_test.py
python -m streamlit run src/ui/app.py
```

실제 음성 인식·AI는 아직 미구현이므로 기본 `stub` 상태로 확인합니다. FFmpeg는 별도 설치해야 합니다.

## 담당자 개발 순서

1. [공통 입력·출력 계약](INPUT_OUTPUT_CONTRACT.md)을 확인합니다.
2. [담당자별 작업](ROLE_GUIDE.md)에서 자신의 파일과 구현할 함수만 확인합니다.
3. `tests/fixtures/contract_samples.py`의 입력 데이터로 자신의 모듈을 **직접 호출**해 독립 테스트합니다.
4. 정상 결과·빈 결과·잘못된 참조·실패 상황을 테스트합니다.
5. 기능이 완성되면 `bootstrap.py`에 자신의 구현체를 등록하고 `.env`에서 해당 구현체(`*_BACKEND` 설정)를 선택합니다.
6. 나머지 모듈은 Stub으로 유지한 채 Streamlit·전체 테스트를 검증하고 PR을 제출합니다.

참고 자료: [아키텍처](ARCHITECTURE.md) · [개발·테스트](DEVELOPMENT_TESTING.md) · [기존 프로젝트 이관](MIGRATION.md)
