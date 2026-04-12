from src.graph.state import GraphState
from src.nodes.rank_node import rank_node
from src.nodes.search_node import search_node


def market_agent(state: GraphState) -> GraphState:
    """Retrieves market postings and computes ranked skill gaps."""
    trace = list(state.agent_trace)
    trace.append("market:start")
    searched_state = search_node(state.model_copy(update={"agent_trace": trace}))
    ranked_state = rank_node(searched_state)
    trace = list(ranked_state.agent_trace)
    trace.append("market:retrieved_and_ranked")
    return ranked_state.model_copy(update={"agent_trace": trace})
