from src.graph.state import GraphState
from src.nodes.parser_node import parser_node


def profile_agent(state: GraphState) -> GraphState:
    """Extracts normalized user skills from resume text."""
    trace = list(state.agent_trace)
    trace.append("profile:start")
    updated_state = parser_node(state)
    trace = list(updated_state.agent_trace)
    trace.append("profile:skills_extracted")
    return updated_state.model_copy(update={"agent_trace": trace})
