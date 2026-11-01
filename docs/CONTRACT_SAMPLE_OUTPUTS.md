# 공통 계약의 실제 JSON 예시 (고정 Fixture 기반)

> **문서 길잡이:** 처음 보는 분은 [시작 가이드](START_HERE.md) → [내 담당 작업](ROLE_IMPLEMENTATION_MANUAL.md)을 먼저 읽으세요. 이 문서는 **필요한 세부 사항을 확인할 때** 사용하는 참고자료입니다.


> **읽는 방법:** 아래는 Pydantic 객체의 `model_dump_json(indent=2)` 결과입니다. 함수는 **JSON이 아닌 Pydantic 객체를 반환**합니다. JSON은 저장/디버깅용 표현입니다.
> **주의:** 마지막 `RenderResult`는 출력 구조를 설명하기 위한 모델 샘플이며 `example_output.mp4` 파일을 생성한 것이 아닙니다. 실제 영상 생성 검증에는 렌더러 테스트가 필요합니다. `source_path`는 설명용 상대 경로로 표기했으며 실제 Pydantic 객체에는 실행 환경에 맞는 절대 경로가 들어갑니다.

| 단계 | 입력/출력 소비자 |
|---|---|
| `VideoAsset` | 업로드 서비스가 생성. Transcriber와 VideoEditor 입력. |
| `Transcript` | 자막 입력. ContentAnalyzer와 SegmentRecommender, UI가 사용. |
| `VideoAnalysis` | 주제·요약 입력. SegmentRecommender와 UI가 사용. |
| `SearchRequest` | UI가 생성. SegmentRecommender 입력. |
| `RecommendationResult` | 검색 결과. PlanService가 EditPlan을 생성할 때 사용. |
| `EditPlan` | 사용자 수정 대기. UI가 버전을 표시하고 수정·승인 요청. |
| `ApprovedEditPlan` | 편집기에서만 수락하는 승인 계약. |
| `RenderResult` | 파일 생성 후 반영할 결과 구조. UI가 재생/다운로드. |

## VideoAsset

업로드 서비스가 생성. Transcriber와 VideoEditor 입력.

```json
{
  "id": "fixture-video-001",
  "project_id": "fixture-project-001",
  "source_path": "examples/demo.mp4",
  "original_name": "demo.mp4",
  "duration_ms": 8000,
  "sha256": "3a078346cff747bfed148428765ccb00474188b9984b0e0a965718467cb275c3",
  "has_audio": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

## Transcript

자막 입력. ContentAnalyzer와 SegmentRecommender, UI가 사용.

```json
{
  "id": "fixture-transcript-001",
  "video_id": "fixture-video-001",
  "language": "ko",
  "segments": [
    {
      "id": "fixture-s1",
      "start_ms": 0,
      "end_ms": 2000,
      "text": "오늘은 인공지능을 소개합니다."
    },
    {
      "id": "fixture-s2",
      "start_ms": 2000,
      "end_ms": 5000,
      "text": "AI는 반복 업무를 자동화합니다."
    },
    {
      "id": "fixture-s3",
      "start_ms": 5000,
      "end_ms": 8000,
      "text": "AI 활용으로 생산성을 높입니다."
    }
  ],
  "transcriber_version": "fixture-transcriber-v1",
  "is_stub": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

## VideoAnalysis

주제·요약 입력. SegmentRecommender와 UI가 사용.

```json
{
  "id": "fixture-analysis-001",
  "video_id": "fixture-video-001",
  "transcript_id": "fixture-transcript-001",
  "summary": "AI 기술과 반복 업무 자동화, 생산성 향상을 설명하는 영상입니다.",
  "topics": [
    {
      "id": "fixture-topic-001",
      "title": "자동화와 생산성",
      "start_ms": 2000,
      "end_ms": 8000,
      "segment_ids": [
        "fixture-s2",
        "fixture-s3"
      ]
    }
  ],
  "analyzer_version": "fixture-analyzer-v1",
  "is_stub": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

## SearchRequest

UI가 생성. SegmentRecommender 입력.

```json
{
  "id": "fixture-request-001",
  "video_id": "fixture-video-001",
  "query": "AI 활용",
  "max_clips": 2,
  "created_at": "2026-01-01T00:00:00Z"
}
```

## RecommendationResult

검색 결과. PlanService가 EditPlan을 생성할 때 사용.

```json
{
  "id": "fixture-recommendation-001",
  "request_id": "fixture-request-001",
  "video_id": "fixture-video-001",
  "transcript_id": "fixture-transcript-001",
  "analysis_id": "fixture-analysis-001",
  "clips": [
    {
      "id": "fixture-clip-001",
      "start_ms": 2000,
      "end_ms": 5000,
      "reason": "AI 사용 사례와 관련된 테스트 추천입니다.",
      "source_segment_ids": [
        "fixture-s2"
      ]
    },
    {
      "id": "fixture-clip-002",
      "start_ms": 5000,
      "end_ms": 8000,
      "reason": "AI 사용 사례와 관련된 테스트 추천입니다.",
      "source_segment_ids": [
        "fixture-s3"
      ]
    }
  ],
  "recommender_version": "fixture-recommender-v1",
  "is_stub": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

## EditPlan

사용자 수정 대기. UI가 버전을 표시하고 수정·승인 요청.

```json
{
  "id": "fixture-plan-001",
  "video_id": "fixture-video-001",
  "request_id": "fixture-request-001",
  "recommendation_id": "fixture-recommendation-001",
  "version": 1,
  "clips": [
    {
      "id": "fixture-clip-001",
      "start_ms": 2000,
      "end_ms": 5000,
      "reason": "AI 사용 사례와 관련된 테스트 추천입니다.",
      "source_segment_ids": [
        "fixture-s2"
      ]
    },
    {
      "id": "fixture-clip-002",
      "start_ms": 5000,
      "end_ms": 8000,
      "reason": "AI 사용 사례와 관련된 테스트 추천입니다.",
      "source_segment_ids": [
        "fixture-s3"
      ]
    }
  ],
  "status": "draft",
  "created_at": "2026-01-01T00:00:00Z",
  "approved_at": null
}
```

## ApprovedEditPlan

편집기에서만 수락하는 승인 계약.

```json
{
  "id": "fixture-plan-001",
  "video_id": "fixture-video-001",
  "request_id": "fixture-request-001",
  "recommendation_id": "fixture-recommendation-001",
  "version": 1,
  "clips": [
    {
      "id": "fixture-clip-001",
      "start_ms": 2000,
      "end_ms": 5000,
      "reason": "AI 사용 사례와 관련된 테스트 추천입니다.",
      "source_segment_ids": [
        "fixture-s2"
      ]
    },
    {
      "id": "fixture-clip-002",
      "start_ms": 5000,
      "end_ms": 8000,
      "reason": "AI 사용 사례와 관련된 테스트 추천입니다.",
      "source_segment_ids": [
        "fixture-s3"
      ]
    }
  ],
  "status": "approved",
  "created_at": "2026-01-01T00:00:00Z",
  "approved_at": "2026-01-01T00:00:00Z"
}
```

## RenderResult

파일 생성 후 반영할 결과 구조. UI가 재생/다운로드.

```json
{
  "id": "fixture-render-001",
  "video_id": "fixture-video-001",
  "plan_id": "fixture-plan-001",
  "plan_version": 1,
  "output_path": "example_output.mp4",
  "duration_ms": 8000,
  "renderer_version": "fixture-renderer-v1",
  "is_stub": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```
