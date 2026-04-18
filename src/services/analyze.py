from src.graph.state import GraphState
from src.graph.workflow import build_workflow


def run_analysis(target_role: str, resume_text: str) -> GraphState:
    app = build_workflow()
    state = GraphState(target_role=target_role, resume_text=resume_text)
    return GraphState.model_validate(app.invoke(state))
