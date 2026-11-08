"""Run the entire two-video Stub workflow without Streamlit."""
from pathlib import Path
import sys

# Run from a fresh checkout even before editable package installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tempfile import TemporaryDirectory

from application.config import Settings
from bootstrap import create_application
from core.models import SearchRequest, new_id


ROOT = Path(__file__).resolve().parents[1]


def main():
    with TemporaryDirectory(prefix="clipnote-smoke-") as folder:
        app = create_application(Settings(runtime_dir=Path(folder)))
        try:
            project = app.create_project("다중 영상 통합 테스트")
            for name in ("lecture.mp4", "interview.mp4"):
                app.add_video(project.id, name, (ROOT / "examples" / "demo.mp4").read_bytes())
            project = app.get_project(project.id)
            project_analysis = app.prepare_project(project.id)
            request = SearchRequest(id=new_id(), project_id=project.id,
                                    video_ids=project.video_ids, query="AI 활용 장면")
            rec = app.recommend(request)
            plan = app.create_plan(project.id, rec.id)
            approved = app.approve_plan(project.id, plan.id, plan.version)
            output = app.render(project.id, approved.id, approved.version)
            print(f"PASS: videos={len(project.video_ids)} analyses={len(project_analysis.video_analysis_ids)}")
            print(f"PASS: recommended_clips={len(rec.clips)} plan_version={approved.version}")
            print(f"PASS: output={output.output_path} stub={output.is_stub}")
            print("NOTE: Stub copies the first input MP4; it does NOT cut/concat selected clips.")
        finally:
            app.close()


if __name__ == "__main__":
    main()
