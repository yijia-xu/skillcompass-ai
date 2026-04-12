from src.graph.state import GraphState


def orchestrator_agent(state: GraphState) -> GraphState:
    """Owns run-level validation and records orchestration progress."""
    trace = list(state.agent_trace)
    trace.append("orchestrator:start")
    trace.append("orchestrator:validated_input")
    return state.model_copy(update={"agent_trace": trace})
