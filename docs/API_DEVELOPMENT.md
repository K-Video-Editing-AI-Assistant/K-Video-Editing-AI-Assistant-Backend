# API 개발 기본 서버

현재 `GET /health`만 제공합니다. 응답은 `{"status":"ok"}`입니다.
업로드·자막·분석·추천·편집 API는 제거했습니다. 기능 담당자가 이후 추가합니다.

## 실행

프로젝트 루트에서 가상환경을 활성화한 뒤 실행합니다.

```bash
python -m pip install -e ".[test]"
python -m uvicorn video_assistant.api.app:app --reload --host 127.0.0.1 --port 8000
```

- Swagger: http://127.0.0.1:8000/docs
- 상태 확인: http://127.0.0.1:8000/health
- OpenAPI: http://127.0.0.1:8000/openapi.json

서버는 영상 처리 서비스·작업 큐를 생성하지 않으며 FFprobe 없이 실행할 수 있습니다.
health는 HTTP 서버 응답만 확인하며 실제 영상 처리 준비 상태를 뜻하지 않습니다.
DB는 사용하지 않습니다. 기존 기능은 파일·JSON 저장을 유지합니다.

## 담당자 작업

- `api/app.py`: 서버 생성과 공통 CORS 설정
- 이후 필요한 기능별 라우터는 `api/routes/`에 추가하고 app.py에서 연결
- 실제 기능은 기존 transcription/analysis/recommendation/editing에서 개발
- API는 기존 ApplicationService를 호출하며 알고리즘을 중복 작성하지 않기
- 기존 샘플 데이터와 직접 호출 테스트 유지

CORS_ORIGINS는 허용할 프론트 주소를 쉼표로 구분합니다.
기본값은 http://localhost:3000,http://localhost:5173 이며 프로젝트 루트 .env로 변경할 수 있습니다.

```bash
python -m pytest -q tests/api
```

전체 테스트는 `python -m pytest -q`입니다. 기존 영상 관련 테스트에는 FFmpeg/FFprobe가 필요합니다.
