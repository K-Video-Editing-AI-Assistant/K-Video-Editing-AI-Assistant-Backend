"""Validate source boundaries and apply a best-effort total duration budget."""

from core.errors import AppError, ErrorCode
from core.models import RecommendationResult, SearchRequest, Transcript


def validate_and_limit_recommendation(
    request: SearchRequest, result: RecommendationResult, transcripts: tuple[Transcript, ...],
) -> RecommendationResult:
    """Keep complete clips in proposed order, within 110% of the target.

    Short or empty results are valid. All clips are validated before filtering.
    Selection improves distance to the target without padding or cutting speech;
    this is a best-effort policy rather than an optimal subset search.
    """
    sources = {t.video_id: t for t in transcripts}
    occupied: dict[str, list[tuple[int, int]]] = {}
    for clip in result.clips:
        transcript = sources.get(clip.video_id)
        if transcript is None:
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 대상 영상이 올바르지 않습니다.")
        lookup = {s.id: (i, s) for i, s in enumerate(transcript.segments)}
        ids = clip.source_segment_ids
        if len(set(ids)) != len(ids) or any(sid not in lookup for sid in ids):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 근거 자막이 올바르지 않습니다.")
        positions = [lookup[sid][0] for sid in ids]
        if positions != list(range(positions[0], positions[0] + len(positions))):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 구간은 연속된 원본 자막이어야 합니다.")
        selected = [lookup[sid][1] for sid in ids]
        if (clip.start_ms != min(s.start_ms for s in selected)
                or clip.end_ms != max(s.end_ms for s in selected)):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 시간이 원본 자막 경계와 다릅니다.")
        previous = occupied.setdefault(clip.video_id, [])
        if any(clip.start_ms < end and start < clip.end_ms for start, end in previous):
            raise AppError(ErrorCode.INVALID_REFERENCE, "추천 구간이 중복되거나 겹칩니다.")
        previous.append((clip.start_ms, clip.end_ms))

    target = request.target_duration_ms
    if target is None:
        return result
    limit = target * 110 // 100
    kept = []
    total = 0
    for clip in result.clips:
        duration = clip.end_ms - clip.start_ms
        if total + duration <= limit and abs(target - total - duration) < abs(target - total):
            kept.append(clip)
            total += duration
    if len(kept) == len(result.clips):
        return result
    kept_ids = {clip.id for clip in kept}
    topics = []
    for topic in result.topics:
        ids = tuple(cid for cid in topic.clip_ids if cid in kept_ids)
        if ids:
            topics.append(topic.model_copy(update={"clip_ids": ids}))
    return RecommendationResult.model_validate({
        **result.model_dump(), "clips": tuple(kept), "topics": tuple(topics),
        "suggested_title": result.suggested_title if kept else "",
    })
