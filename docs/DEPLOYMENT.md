# develop 통합과 FastAPI Cloud 자동 배포

## 브랜치 흐름

`feature/기능명 → develop → main → FastAPI Cloud`

- 최신 develop에서 기능 브랜치를 만들고 develop으로 PR을 제출합니다.
- develop에서 기능을 통합·검증합니다. develop 자체는 배포하지 않습니다.
- 릴리스 시 develop에서 main으로 PR을 제출합니다.
- main에 변경이 반영되면 전체 테스트를 다시 실행하고 성공한 같은 커밋을 배포합니다.
- 직접 push도 배포 트리거가 되므로 main은 GitHub 브랜치 보호로 PR만 허용하도록 설정하는 것이 좋습니다.

## 구성 파일

| 파일 | 역할 |
|---|---|
| `.github/workflows/ci.yml` | develop/main PR, develop push의 전체 테스트 및 재사용 가능한 릴리스 테스트 |
| `.github/workflows/deploy.yml` | main push 후 CI 성공 시 FastAPI Cloud 배포 |
| `pyproject.toml` | 배포 CLI 선택 의존성 및 `video_assistant.api.app:app` 진입점 |
| `.python-version` | Python 3.11 선택 |
| `.fastapicloudignore` | 테스트·문서·예제 등 배포 제외 |

CI는 Ubuntu에 FFmpeg/FFprobe를 설치하고 `python -m pip install -e '.[test]'` 후 전체 테스트를 실행합니다.
PR 테스트에는 배포 비밀키를 전달하지 않습니다. 배포 비밀키는 main 배포 단계에만 전달합니다.
실행 중인 배포를 중간에 취소하지 않도록 배포 실행을 직렬화했습니다.

## 최초 연결 (계정 소유자 작업)

1. FastAPI Cloud에 로그인하여 이 저장소용 앱을 생성하거나 기존 앱을 선택합니다.
2. 대시보드에서 앱 ID와 이 앱의 배포 토큰을 확인/생성합니다.
3. GitHub 저장소 → Settings → Secrets and variables → Actions에 다음 **repository secrets**를 등록합니다.
   - `FASTAPI_CLOUD_TOKEN`: 해당 앱의 배포 토큰
   - `FASTAPI_CLOUD_APP_ID`: 앱 UUID (앱 이름이나 URL이 아님)
4. Cloud 환경 변수의 CORS_ORIGINS를 실제 프론트 주소로 설정합니다. 아직 프론트 배포 전이면 개발 주소 기본값으로 시작할 수 있습니다.
5. Cloud의 GitHub 직접 자동 배포를 함께 켜지 않습니다. 테스트를 통과한 GitHub Actions 배포만 사용합니다.
6. 검토 후 이 설정을 develop에 병합하고, develop → main 릴리스 PR을 병합합니다.
7. Actions에서 Verify release 및 Deploy to FastAPI Cloud 성공을 확인합니다.
8. Cloud가 제공한 실제 URL의 `/health`, `/docs`로 접속해 확인합니다.

배포 토큰은 채팅이나 코드에 붙이지 않습니다. 만료되면 Secrets를 갱신해야 합니다.
Cloud 앱 생성·토큰 등록·실제 배포는 완료 여부를 별도로 확인해야 합니다. YAML 작성만으로 계정 연결이 완료되는 것은 아닙니다.

## PR 검증·보호 규칙

GitHub에서 develop과 main에 PR 요구 및 CI 필수 통과를 설정합니다. 실제 Actions 실행 후 표시되는 테스트 체크 이름을 선택합니다.
main에는 develop의 릴리스 PR을 사용합니다. 이 경로는 팀 규칙이며 현재 워크플로가 PR 출발 브랜치를 강제하지는 않습니다.
이 문서는 승인 수나 Squash/Merge 방식은 새로 지정하지 않습니다.

## 현재 배포 범위

현재 서버는 `/health`와 Swagger만 제공합니다. DB나 영상 API는 추가하지 않습니다.
영상 API 추가 시 로컬 파일·JSON 저장이 재배포/인스턴스 교체 후 유지되는지, 여러 인스턴스에서 공유 가능한지 먼저 검토해야 합니다.
기존 파일 저장·프로세스 내부 작업 큐를 클라우드 운영용으로 검증한 것은 아닙니다.
향후 실제 편집을 배포할 때는 Cloud 환경에서 FFmpeg 설치 지원과 실행 시간/메모리 조건도 별도 확인합니다.

## 공식 참고

- [FastAPI 앱 진입점](https://fastapicloud.com/docs/builds-and-deployments/configuring-fastapi/)
- [GitHub Actions용 배포 토큰](https://fastapicloud.com/docs/advanced-features/deploy-tokens/)
- [배포 파일 제외](https://fastapicloud.com/docs/builds-and-deployments/fastapicloudignore/)

## 현재 연결된 앱

- Cloud 앱: `K-Video-Editing-AI-Assistant-Backend`
- 앱 ID: `66174a91-5322-430a-84e4-7f2e157d7cf0`
- 예정 서비스 주소: https://k-video-editing-ai-assistant-backend.fastapicloud.dev
- GitHub repository secrets의 FASTAPI_CLOUD_TOKEN / FASTAPI_CLOUD_APP_ID 등록 완료.
- 실제 서비스 응답은 첫 main 배포 성공 후 확인합니다.
