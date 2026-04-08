from langgraph.graph import END, START, StateGraph

from src.graph.state import GraphState
from src.nodes.parser_node import parser_node
from src.nodes.planner_node import planner_node
from src.nodes.rank_node import rank_node
from src.nodes.search_node import search_node


def build_workflow():
    graph = StateGraph(GraphState)
    graph.add_node("parser", parser_node)
    graph.add_node("search", search_node)
    graph.add_node("rank", rank_node)
    graph.add_node("planner", planner_node)

    graph.add_edge(START, "parser")
    graph.add_edge("parser", "search")
    graph.add_edge("search", "rank")
    graph.add_edge("rank", "planner")
    graph.add_edge("planner", END)
    return graph.compile()
