from src.graph.state import GraphState
from src.nodes.planner_node import planner_node


def planning_agent(state: GraphState) -> GraphState:
    """Builds staged learning plans from ranked gaps."""
    trace = list(state.agent_trace)
    trace.append("planning:start")
    planned_state = planner_node(state.model_copy(update={"agent_trace": trace}))
    trace = list(planned_state.agent_trace)
    trace.append("planning:plan_generated")
    return planned_state.model_copy(update={"agent_trace": trace})
