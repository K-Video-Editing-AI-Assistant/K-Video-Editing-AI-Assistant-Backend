"""Print an exact, deterministic example of how contract objects refer to each other.

Run from the repository root after an editable install:
    python scripts/show_contract_chain.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tests.fixtures.contract_samples import (
    sample_analysis, sample_approved_plan, sample_draft,
    sample_recommendation, sample_request, sample_transcript, sample_video,
)


def main() -> None:
    video = sample_video()
    transcript = sample_transcript(video)
    analysis = sample_analysis(transcript)
    request = sample_request(video)
    recommendation = sample_recommendation(request, transcript, analysis)
    draft = sample_draft(recommendation)
    approved = sample_approved_plan(recommendation)

    print("1. VideoAsset", video.id, f"({video.duration_ms}ms)")
    print("2. Transcript", transcript.id, "-> video_id", transcript.video_id)
    print("3. VideoAnalysis", analysis.id, "-> transcript_id", analysis.transcript_id)
    print("4. SearchRequest", request.id, "-> video_id", request.video_id)
    print("5. RecommendationResult", recommendation.id, "-> analysis_id", recommendation.analysis_id)
    print("   clips:")
    for clip in recommendation.clips:
        print(f"   - {clip.start_ms}~{clip.end_ms}ms", clip.source_segment_ids, clip.reason)
    print("6. EditPlan", draft.id, "-> recommendation_id", draft.recommendation_id)
    print("7. ApprovedEditPlan", approved.id, "-> status", approved.status.value)
    assert video.id == transcript.video_id == analysis.video_id == recommendation.video_id
    assert transcript.id == analysis.transcript_id == recommendation.transcript_id
    assert recommendation.id == draft.recommendation_id
    assert approved.clips == draft.clips
    print("PASS: linked IDs, clip ordering and Pydantic contracts are consistent")
    print("(These are fixture objects only; this script does not perform AI or rendering.)")


if __name__ == "__main__":
    main()
