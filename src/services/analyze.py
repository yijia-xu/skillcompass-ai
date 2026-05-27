from src.graph.state import GraphState
from src.graph.workflow import build_workflow


def run_analysis(
    target_role: str, resume_text: str, resume_file_path: str = "", weekly_hours: int = 8
) -> GraphState:
    app = build_workflow(include_planning=True)
    state = GraphState(
        target_role=target_role,
        resume_text=resume_text,
        resume_file_path=resume_file_path,
        weekly_hours=weekly_hours,
    )
    return GraphState.model_validate(app.invoke(state))


def run_gap_analysis(
    target_role: str, resume_text: str, resume_file_path: str = "", weekly_hours: int = 8
) -> GraphState:
    """Run only up to skill gap ranking (no roadmap generation)."""
    app = build_workflow(include_planning=False)
    state = GraphState(
        target_role=target_role,
        resume_text=resume_text,
        resume_file_path=resume_file_path,
        weekly_hours=weekly_hours,
    )
    return GraphState.model_validate(app.invoke(state))
