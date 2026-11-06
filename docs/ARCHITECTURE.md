# CLIPNOTE 아키텍처 — 단일 Python 앱

## 5개 역할과 코드 소유권

| 역할 | 담당 영역 | 책임 |
|---|---|---|
| PM | `core/`, `docs/` | 공통 모델·인터페이스·검증 정책·통합 규칙 관리 |
| UI(프론트) | `ui/` | Streamlit 화면과 사용자 입력; `ApplicationService`만 호출 |
| AI 영상분석 | `ai/` | 자막 전처리, 영상 분석, 프로젝트 키워드, 자연어 검색·추천 |
| 영상처리 | `processing/` | MP4 저장·FFprobe, Whisper, FFmpeg, SRT 저장 |
| Application 담당 | `application/`, `bootstrap.py` | 워크플로, 작업자, 결과 저장·조회, 계획 검증·승인, 객체 연결 |

**Application 담당**은 별도 HTTP 서버를 만들지 않고, 같은 Python 프로세스의 `ApplicationService`를 구현·관리합니다. UI의 요청을 받아 AI 영상분석·영상처리 모듈을 연결하고 결과를 검증·저장합니다.

## 호출 흐름

```text
Streamlit UI  (ui/app.py)
    |
    v
ApplicationService  (application/service.py)
    |-- processing/files.py: 업로드·FFprobe
    |-- Transcriber: VideoAsset -> Transcript
    |-- TranscriptPreprocessor: Transcript -> ProcessedTranscript
    |-- ContentAnalyzer: ProcessedTranscript -> VideoAnalysis
    |-- ProjectAnalyzer: Project + analyses -> ProjectAnalysis
    |-- SegmentRecommender: SearchRequest + data -> RecommendationResult
    |-- PlanService: RecommendationResult -> EditPlan -> ApprovedEditPlan
    `-- VideoEditor: videos + transcripts + approved plan -> RenderResult
    |
    `-- ProjectStore & JobScheduler: JSON·영상·작업 상태 저장
```

AI 모듈과 영상처리 모듈은 **서로의 실제 구현체를 import하지 않습니다**. Application 계층이 공통 인터페이스로 두 모듈을 호출합니다.

## 영상·AI 결과 재사용

- `Project` 하나에는 영상 여러 개가 속합니다.
- 자막과 영상별 분석은 `VideoAsset.id`를 기준으로 저장됩니다.
- 자연어 요청이 달라지면 기존 준비 결과를 재사용하고 추천만 다시 실행합니다.
- 원본 자막과 전처리 자막은 분리하고 원본 발언 ID를 보존합니다.
- 추천 클립(수정하지 않는 AI 결과)과 실제 편집 클립(수정 가능한 사용자 계획)은 분리합니다.

## 저장 경로

```text
runtime/
├── jobs/<job_id>.json
└── projects/<project_id>/
    ├── project.json
    ├── project_analysis.json
    ├── videos/<video_id>/
    │   ├── source.mp4
    │   ├── video.json
    │   ├── transcript.json
    │   ├── transcript.srt
    │   ├── processed.json
    │   └── analysis.json
    ├── recommendations/<recommendation_id>.json
    ├── plans/<plan_id>_v<version>_<status>.json
    ├── latest_plan.json
    └── outputs/<plan_id>_v<version>.mp4
```

`runtime/`은 `.gitignore`로 제외합니다. 단일 Python 프로세스 기준이며 여러 프로세스 동시 편집, 자동 작업 복구, 권한 인증 및 클라우드 저장은 포함되지 않습니다.

## 합의된 의존성 방향

`ui → application → core.interfaces → ai/processing`이며, `core`는 어떤 구현 모듈도 import하지 않습니다. 실제 연결은 `bootstrap.py`가 책임집니다.
