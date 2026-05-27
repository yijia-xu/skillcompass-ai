from langgraph.graph import END, START, StateGraph

from src.agents.market_agent import market_agent
from src.agents.orchestrator_agent import orchestrator_agent
from src.agents.planning_agent import planning_agent
from src.agents.profile_agent import profile_agent
from src.graph.state import GraphState


def build_workflow(include_planning: bool = True):
    graph = StateGraph(GraphState)
    graph.add_node("orchestrator", orchestrator_agent)
    graph.add_node("profile", profile_agent)
    graph.add_node("market", market_agent)
    if include_planning:
        graph.add_node("planning", planning_agent)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "profile")
    graph.add_edge("profile", "market")
    if include_planning:
        graph.add_edge("market", "planning")
        graph.add_edge("planning", END)
    else:
        graph.add_edge("market", END)
    return graph.compile()
