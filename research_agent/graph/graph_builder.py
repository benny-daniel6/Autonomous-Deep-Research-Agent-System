"""
LangGraph graph construction — wires all nodes, edges, and routing.

The compiled graph is exposed as ``research_graph`` for use by the
FastAPI app and Streamlit UI.

Graph topology::

    START
      │
      ▼
    memory_check_node ──┐
      │                 │
      │ (miss)          │ (hit)
      ▼                 ▼
    planner_node    report_from_memory_node ──► END
      │
      │  fan_out (Send × N subtasks)
      ▼
    search_worker ──► aggregate_search
                          │
                          │  fan_out (Send × N subtasks)
                          ▼
                    summarizer_worker ──► critic_node
                                            │
                          ┌─────────────────┼─────────────────┐
                          │ PASS            │ REVISE           │ FAIL
                          ▼                 ▼                  ▼
                    report_node      planner_node        error_handler_node
                          │          (retry loop)              │
                          ▼                                    ▼
                         END                                  END
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from research_agent.graph.nodes.critic import critic_node, route_after_critic
from research_agent.graph.nodes.error_handler import error_handler_node
from research_agent.graph.nodes.memory_check import (
    memory_check_node,
    route_after_memory_check,
)
from research_agent.graph.nodes.planner import planner_node
from research_agent.graph.nodes.report import report_from_memory_node, report_node
from research_agent.graph.nodes.search import (
    aggregate_search_node,
    fan_out_to_search,
    search_worker_node,
)
from research_agent.graph.nodes.summarizer import (
    fan_out_to_summarize,
    summarizer_worker_node,
)
from research_agent.graph.state import AgentState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Construct and return the **uncompiled** ``StateGraph``.

    Call ``.compile()`` on the result to get a runnable graph.
    Keeping build and compile separate lets callers inject
    checkpointers or other configuration before compiling.
    """

    builder = StateGraph(AgentState)

    # ── Register nodes ──────────────────────────────────────────────────

    builder.add_node("memory_check_node", memory_check_node)
    builder.add_node("planner_node", planner_node)
    builder.add_node("search_worker", search_worker_node)
    builder.add_node("aggregate_search", aggregate_search_node)
    builder.add_node("summarizer_worker", summarizer_worker_node)
    builder.add_node("critic_node", critic_node)
    builder.add_node("report_node", report_node)
    builder.add_node("report_from_memory_node", report_from_memory_node)
    builder.add_node("error_handler_node", error_handler_node)

    # ── Edges ───────────────────────────────────────────────────────────

    # Entry point
    builder.add_edge(START, "memory_check_node")

    # Memory check → cached report or fresh planning
    builder.add_conditional_edges(
        "memory_check_node",
        route_after_memory_check,
        {
            "report_from_memory_node": "report_from_memory_node",
            "planner_node": "planner_node",
        },
    )

    # Planner → fan-out to parallel search workers (Send × N)
    builder.add_conditional_edges("planner_node", fan_out_to_search)

    # All search workers converge at the aggregate sync barrier
    builder.add_edge("search_worker", "aggregate_search")

    # Aggregate → fan-out to parallel summarizer workers (Send × N)
    builder.add_conditional_edges("aggregate_search", fan_out_to_summarize)

    # All summarizer workers converge at the critic
    builder.add_edge("summarizer_worker", "critic_node")

    # Critic → report / retry / error
    builder.add_conditional_edges(
        "critic_node",
        route_after_critic,
        {
            "report_node": "report_node",
            "planner_node": "planner_node",
            "error_handler_node": "error_handler_node",
        },
    )

    # Terminal edges
    builder.add_edge("report_node", END)
    builder.add_edge("report_from_memory_node", END)
    builder.add_edge("error_handler_node", END)

    logger.info("Research graph built successfully.")
    return builder


# ── Pre-compiled graph for direct import ────────────────────────────────────

research_graph = build_graph().compile()
