"""
Tests for the LangGraph compilation and topology.
"""

from research_agent.graph.graph_builder import build_graph, research_graph


def test_graph_compiles():
    """Verify that the StateGraph compiles successfully without schema errors."""
    assert research_graph is not None
    assert hasattr(research_graph, "ainvoke")


def test_graph_nodes_exist():
    """Check that all required nodes are present in the compiled graph."""
    nodes = research_graph.nodes.keys()
    expected_nodes = {
        "__start__",
        "memory_check_node",
        "planner_node",
        "search_worker",
        "aggregate_search",
        "summarizer_worker",
        "critic_node",
        "report_node",
        "report_from_memory_node",
        "error_handler_node"
    }
    assert expected_nodes.issubset(nodes)
