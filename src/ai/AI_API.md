# AI 관련 API

> 현재 `src/api/main.py`에는 `/api/v1/health`만 등록되어 있습니다. 이 문서는 AI 담당자가 제공하는 입력/출력 계약입니다. **4개 HTTP 라우트 자체는 아직 Application 담당자가 구현해야 합니다.**

## 1. POST `/api/videos/{videoId}/analysis`

- **Request:** Path `videoId` (string), Body 없음.
- **Response:** `202 Accepted` — 아래 JSON은 Application이 생성하는 형식입니다.

```json
{
    "job_id": "<jobId>",
    "video_id": "<videoId>",
    "kind": "prepare",
    "state": "queued",
    "progress": 0,
    "status_url": "/api/jobs/<jobId>"
}
```

- **AI 처리:** `Transcript → ProcessedTranscript → VideoAnalysis`, 그리고 `Project + VideoAnalysis[] → ProjectAnalysis`.
- **비고:** Whisper 생성, Job 생성·저장, 결과 저장은 Application/영상처리 담당. 현재 prepare Job은 **프로젝트 단위**이므로 `videoId` 기반 API의 연결 방식은 Application에서 결정해야 합니다.

## 2. GET `/api/videos/{videoId}/analysis`

- **Request:** Path `videoId` (string), Body 없음.
- **Response:** `200 OK` — `build_analysis_response(video_id, analysis, project_analysis).model_dump(mode="json")`.

```json
{
    "video_id": "<videoId>",
    "video_analysis_id": "<analysisId>",
    "project_analysis_id": "<projectAnalysisId>",
    "summary": "숲의 역할",
    "topics": [
        {
            "id": "<topicId>",
            "title": "탄소 흡수",
            "description": "...",
            "start_ms": 0,
            "end_ms": 30000,
            "source_segment_ids": [
                "<segmentId>"
            ]
        }
    ],
    "suggested_keywords": [
        {
            "keyword": "탄소 흡수",
            "reason": "주요 주제",
            "topic_ids": [
                "<topicId>"
            ]
        }
    ],
    "analyzer_version": "gemini-content-analyzer-v1:...",
    "is_stub": false
}
```

- **주의:** 프로젝트 키워드는 조회 대상 영상 주제에 연결된 것만 포함합니다. 조회 시 Gemini를 재호출하지 않습니다.

## 3. POST `/api/videos/{videoId}/recommendations`

- **Request:** Path `videoId` (string), JSON Body 아래 형식.

```json
{
    "query": "탄소 흡수 장면을 찾아줘",
    "topic_id": "<topicId>",
    "max_duration_ms": 60000,
    "max_clips": 5,
    "edit_mode": "preserve_order"
}
```

| 필드 | 필수 | 기준 |
|---|---|---|
| `query` | 조건부 | 자연어 요청, 입력 시 공백 불가 |
| `topic_id` | 조건부 | 해당 영상 `topics[].id` |
| `max_duration_ms` | 선택 | 양의 정수 또는 `null`; 30초=30000, 1분=60000 |
| `max_clips` | 선택 | 1~20, 기본 5 |
| `edit_mode` | 선택 | `preserve_order`(기본), `group_by_topic` |

`query`와 `topic_id` 중 하나 이상 필요합니다.

- **Response:** `202 Accepted` — 
```json
{
    "job_id": "<jobId>",
    "video_id": "<videoId>",
    "kind": "recommend",
    "state": "queued",
    "progress": 0,
    "status_url": "/api/jobs/<jobId>"
}
```
- **AI 처리:** `SceneRecommendationInput.model_validate(body)` → `recommend_scene(recommender, project, video_id, transcript, analysis, project_analysis, options)`.
- **저장:** 반환된 `SceneRecommendationOutcome.request`와 `.result`를 Application 저장소에 함께 저장해야 합니다. 목표 길이는 **선택된 클립의 전체 길이 합계**에 적용하며, 클립을 중간에서 자르지 않습니다.

## 4. GET `/api/videos/{videoId}/recommendations/{recommendationId}`

- **Request:** Path `videoId`, `recommendationId` (string), Body 없음.
- **Response:** `200 OK` — `build_recommendation_response(video_id, request, result).model_dump(mode="json")`.

```json
{
    "recommendation_id": "<recommendationId>",
    "video_id": "<videoId>",
    "request_id": "<requestId>",
    "project_analysis_id": "<projectAnalysisId>",
    "suggested_title": "탄소 흡수",
    "total_duration_ms": 30000,
    "clips": [
        {
            "id": "<clipId>",
            "video_id": "<videoId>",
            "start_ms": 0,
            "end_ms": 30000,
            "reason": "탄소 흡수 원리를 설명함",
            "source_segment_ids": [
                "<segmentId>"
            ]
        }
    ],
    "topics": [
        {
            "id": "<groupId>",
            "title": "탄소 흡수",
            "description": "...",
            "clip_ids": [
                "<clipId>"
            ]
        }
    ],
    "recommender_version": "gemini-recommender-v1:...",
    "is_stub": false
}
```

- **주의:** `request`는 생성 때 함께 저장한 **원본 SearchRequest**입니다. 클립 0개인 결과도 다른 영상에서 조회되지 않도록 요청의 video ID와 result ID를 검증합니다.

## 비동기 Job과 오류

- 최초 POST 응답: `202` + `job_id`.
- 프론트엔드: `GET /api/jobs/{jobId}` 반복 조회.
- 완료 시 `JobStatus.result_ref`: `prepare` → **ProjectAnalysis.id**, `recommend` → **RecommendationResult.id**. (`job_id`와 다릅니다.)
- HTTP 응답 보완 제안: `result_type`, `result_url`을 Application이 생성하여 프론트엔드에 제공.
- 즉시 발생한 잘못된 입력·참조는 400/422, 없는 객체는 404, 분석 미완료는 409로 제안. 비동기 AI 실패는 `state=failed`로 조회해야 합니다. `Core.ErrorCode`를 HTTP 상태에 매핑하는 것은 Application 담당.

## 수정 범위와 남은 연결

- AI 담당: `src/ai/api_adapter.py`, `src/ai/api_contract.py` (요청 검증·클립 추천·GET AI 결과 JSON 변환).
- Application 담당: FastAPI 4개 라우트, `videoId → projectId` 조회, 기존 prepare Job의 프로젝트 범위 조정, 저장된 `SearchRequest` 조회 메서드, `Job.result_ref → result_url` 조합, 오류 응답.
- Core 모델, HTTP 라우터, Job 코드, Bootstrap은 이번 패치에서 수정하지 않았습니다.
