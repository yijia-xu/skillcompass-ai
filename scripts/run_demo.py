import json
from pathlib import Path

from pypdf import PdfReader

from src.graph.state import GraphState
from src.graph.workflow import build_workflow


def load_resume_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text()


def to_markdown(result: GraphState) -> str:
    lines = [f"# GapSolver AI Report ({result.target_role})", ""]
    lines.append("## Top Skill Gaps")
    for g in result.top_skill_gaps:
        lines.append(f"- **{g.skill}** (score: {g.gap_score}) - {g.reason}")
    lines.append("")
    lines.append("## 3-Phase Learning Plan")
    for step in result.learning_plan:
        lines.append(f"### {step.phase}")
        lines.append(f"- Objective: {step.objective}")
        lines.append(f"- Deliverable: {step.deliverable}")
        lines.append("- Tasks:")
        for task in step.tasks:
            lines.append(f"  - {task}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    resume_path = root / "examples" / "sample_resume.txt"
    output_json = root / "examples" / "sample_output.json"
    output_md = root / "examples" / "sample_output.md"

    state = GraphState(
        target_role="data_engineer",
        resume_text=load_resume_text(resume_path),
    )

    app = build_workflow()
    result: GraphState = app.invoke(state)

    output_json.write_text(json.dumps(result.model_dump(), indent=2, ensure_ascii=True))
    output_md.write_text(to_markdown(result))
    print(f"Saved demo outputs to {output_json} and {output_md}")


if __name__ == "__main__":
    main()
