# 아키텍처 및 공통 계약 — 스켈레톤 v1

> **문서 길잡이:** 처음 보는 분은 [시작 가이드](START_HERE.md) → [내 담당 작업](ROLE_IMPLEMENTATION_MANUAL.md)을 먼저 읽으세요. 이 문서는 **필요한 세부 사항을 확인할 때** 사용하는 참고자료입니다.


## 실행 흐름

```text
Streamlit UI
  └── ApplicationService (core/workflow.py)
        ├── FileProjectStore (core/storage.py)
        ├── DefaultPlanService (core/plan_service.py)
        ├── ThreadJobScheduler (core/jobs.py)
        ├── Transcriber -> StubTranscriber
        ├── ContentAnalyzer -> StubContentAnalyzer
        ├── SegmentRecommender -> StubSegmentRecommender
        └── VideoEditor -> StubVideoEditor

bootstrap.py에서 모든 구체 구현체 연결 및 혼합 모드 선택
```

## 공개 계약

- `core/models.py`의 Pydantic v2 클래스가 **유일한 공통 데이터 정의**입니다.
- `core/interfaces.py`의 ABC는 UI 및 모듈 간 공개 계약입니다.
- 이전 v1 계약에 `ProjectStore.get_transcript(transcript_id)`, `ProjectStore.get_analysis(analysis_id)` 및 `ApplicationService.get_video(video_id)` 조회 메서드를 추가했습니다. 이전 계약 패키지와 완전히 동일하지 않으므로 팀원에게 이 패키지를 새 기준으로 공유하세요.
- 시간은 정수 밀리초, `[start_ms, end_ms)`이고, `clips` 순서가 영상 순서입니다.
- API 키, FFmpeg 실행 정보, AI 프롬프트 등은 인터페이스 외부의 모듈 구현 내부에서 관리합니다.

## 필수 상태 규칙

- 영상 준비 작업(`prepare`): `transcribing` → `analyzing` 후 `VideoAnalysis.id` 반환. 같은 영상·버전의 자막/분석 결과는 재사용.
- 구간 추천 작업(`recommend`): `SearchRequest`마다 새 결과 반환. 추천 없음은 `clips=()`.
- 초안 생성: `EditPlan(version=1,status=draft)`.
- 초안 수정: version + 1, 이전 version/status를 함께 검사.
- 초안 승인: 같은 version에서 `approved`로 상태만 변경, 최소 1개 클립 필요.
- 편집 작업(`render`): `ApprovedEditPlan`만 사용, 출력 파일은 FFprobe로 검사.
- 작업 상태: `queued` → `running` → `succeeded` 또는 `failed`, 결과 ID는 `result_ref`에 저장.

## 파일 저장 구조

```text
runtime/
├── projects/<project_id>/
│   ├── source.mp4
│   └── outputs/render_<job_id>.mp4
└── records/
    ├── videos/<id>.json
    ├── transcripts/<id>.json
    ├── analyses/<id>.json
    ├── requests/<id>.json
    ├── recommendations/<id>.json
    ├── plans/<plan_id>/current.json
    ├── plans/<plan_id>/v1.json, v2.json, ...
    ├── renders/<id>.json
    └── jobs/<id>.json
```

각 레코드는 모델 자체를 JSON 직렬화한 것으로 ID와 본문을 함께 저장합니다. 플랜 현재값 갱신은 동일 프로세스 잠금 아래 처리하며, 기록마다 `os.replace`를 사용합니다. **두 파일을 하나의 트랜잭션으로 쓰지 않기 때문에 디스크/프로세스 비정상 종료 시 완전한 내구성을 보장하지 않습니다.**

## 구현 순서

1. 전원: `models.py`, `interfaces.py` 계약 검토.
2. 공통 담당: `storage.py`, `plan_service.py`, `jobs.py`, `workflow.py` 유지/추가 테스트.
3. 담당 2/3/4/5: 각자 실제 어댑터 구현 및 단위/계약 테스트.
4. 담당 1: UI 기능 개선 및 실제 처리 결과 표시.
5. 담당자: 독립 테스트를 마친 뒤 자기 브랜치에서 `bootstrap.py`에 구현체 등록, Stub/Real 혼합 통합 테스트. 팀장: PR 검토 및 main 병합 후 전체 흐름 검증.

## 안전/운영 제약

- Stub 추천은 실제 의미 검색이 아니고, Stub 렌더링은 잘라내기를 수행하지 않습니다.
- 업로드는 `.mp4` 확장자와 FFprobe의 실제 video stream을 검사하고 업로드 최대 크기를 제한합니다.
- 허용되지 않은 파일 이름은 저장 경로 생성에 사용하지 않습니다. 원본은 `source.mp4`로 저장됩니다.
- FFmpeg 어댑터는 사용자 문자열을 shell에 넣지 말고 인자 배열 `subprocess.run([...], shell=False)`를 사용합니다.
- 작업자 스레드는 Streamlit API를 호출하지 않습니다. UI는 저장된 상태를 조회합니다.
- 동일 런타임 경로를 여러 서버 프로세스에서 공유하면 계획 CAS/작업 복구가 깨질 수 있습니다.
- DB 권한 제어, 다중 사용자 격리, 요청별 사용자 인가 등은 포함하지 않습니다. 신뢰할 수 있는 로컬 개발 환경에서 사용하세요.
- Stub/Real 캐시 구분은 각 클래스의 `VERSION`을 통해 합니다. 실제 모델/프롬프트 설정 변경 시 `VERSION`을 갱신해야 합니다.
