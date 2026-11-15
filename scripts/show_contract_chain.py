"""Print complete shared Pydantic JSON objects and their reference relationships."""
from pathlib import Path
import sys

# Run from a fresh checkout even before editable package installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tempfile import TemporaryDirectory

from application.config import Settings
from bootstrap import create_application
from core.models import SearchRequest, new_id


ROOT = Path(__file__).resolve().parents[1]


with TemporaryDirectory(prefix="ai-video-assistant-contract-") as folder:
    app = create_application(Settings(runtime_dir=Path(folder)))
    try:
        project = app.create_project("계약 JSON 예제")
        asset = app.add_video(project.id, "demo.mp4", (ROOT / "examples" / "demo.mp4").read_bytes())
        transcript_analysis = app.prepare_project(project.id)
        request = SearchRequest(id=new_id(), project_id=project.id,
                                video_ids=(asset.id,), query="AI 관련 내용")
        result = app.recommend(request)
        plan = app.create_plan(project.id, result.id)
        print("\n[Transcript]")
        print(app.get_transcript(project.id, asset.id).model_dump_json(indent=2))
        print("\n[ProjectAnalysis]")
        print(transcript_analysis.model_dump_json(indent=2))
        print("\n[RecommendationResult]")
        print(result.model_dump_json(indent=2))
        print("\n[EditPlan]")
        print(plan.model_dump_json(indent=2))
        print("\n[ID references]")
        print("recommendation.request_id == request.id:", result.request_id == request.id)
        print("editplan.recommendation_id == result.id:", plan.recommendation_id == result.id)
    finally:
        app.close()
