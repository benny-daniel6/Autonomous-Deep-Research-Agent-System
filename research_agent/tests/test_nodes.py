"""
Tests for LangGraph nodes and their state transitions.

Uses mocks to avoid hitting real LLMs or Search APIs during testing,
ensuring unit tests remain fast and deterministic.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from research_agent.graph.nodes.critic import critic_node, route_after_critic
from research_agent.graph.nodes.error_handler import error_handler_node
from research_agent.graph.nodes.memory_check import (
    memory_check_node,
    route_after_memory_check,
)
from research_agent.graph.nodes.planner import planner_node
from research_agent.graph.nodes.report import report_from_memory_node, report_node
from research_agent.graph.nodes.search import search_worker_node
from research_agent.graph.nodes.summarizer import summarizer_worker_node
from research_agent.models.schemas import (
    AgentError,
    Critique,
    MemoryHit,
    Plan,
    Report,
    SearchResult,
    SubTask,
    Summary,
)


@pytest.fixture
def mock_llm_response():
    """Returns a mock LLM that returns whatever object is passed to it."""
    def _create_mock(return_val):
        llm = MagicMock()
        llm_with_structured = MagicMock()
        llm_with_structured.ainvoke = AsyncMock(return_value=return_val)
        llm.with_structured_output.return_value = llm_with_structured
        return llm
    return _create_mock


# ── Memory Check Node Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("research_agent.graph.nodes.memory_check.get_memory_store")
async def test_memory_check_node_miss(mock_get_store):
    store = MagicMock()
    store.query.return_value = []
    mock_get_store.return_value = store

    state = {"query": "test query"}
    result = await memory_check_node(state)

    assert result["memory_hits"] == []
    assert "memory_check_latency_s" in result["metadata"]


@pytest.mark.asyncio
@patch("research_agent.graph.nodes.memory_check.get_memory_store")
async def test_memory_check_node_hit(mock_get_store):
    store = MagicMock()
    store.query.return_value = [
        MemoryHit(
            query="test query",
            report_summary="test summary",
            similarity_score=0.9,
        )
    ]
    mock_get_store.return_value = store

    state = {"query": "test query"}
    result = await memory_check_node(state)

    assert len(result["memory_hits"]) == 1
    assert result["memory_hits"][0].similarity_score == 0.9


def test_route_after_memory_check():
    assert route_after_memory_check({"memory_hits": []}) == "planner_node"
    assert route_after_memory_check({"memory_hits": [MagicMock()]}) == "report_from_memory_node"


# ── Planner Node Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("research_agent.graph.nodes.planner.get_llm")
async def test_planner_node_success(mock_get_llm, mock_llm_response):
    mock_plan = Plan(
        subtasks=[
            SubTask(id="sub_1", description="desc 1", search_queries=["q1", "q2"], priority=1),
            SubTask(id="sub_2", description="desc 2", search_queries=["q3", "q4"], priority=2),
        ],
        reasoning="Test reasoning"
    )
    mock_get_llm.return_value = mock_llm_response(mock_plan)

    state = {"query": "test query"}
    result = await planner_node(state)

    assert result["plan"] == mock_plan
    assert result["retry_count"] == 0
    assert "planner_latency_s" in result["metadata"]


@pytest.mark.asyncio
@patch("research_agent.graph.nodes.planner.get_llm")
async def test_planner_node_with_retry_critique(mock_get_llm, mock_llm_response):
    mock_plan = Plan(
        subtasks=[
            SubTask(id="sub_1", description="desc 1", search_queries=["q1", "q2"], priority=1),
            SubTask(id="sub_2", description="desc 2", search_queries=["q3", "q4"], priority=2),
        ],
        reasoning="Test reasoning"
    )
    mock_get_llm.return_value = mock_llm_response(mock_plan)

    state = {
        "query": "test query",
        "retry_count": 0,
        "critique": Critique(verdict="REVISE", gaps=["Missing info"], reasoning="test")
    }
    result = await planner_node(state)

    assert result["plan"] == mock_plan
    assert result["retry_count"] == 1


# ── Critic Node Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("research_agent.graph.nodes.critic.get_llm")
async def test_critic_node_pass(mock_get_llm, mock_llm_response):
    mock_critique = Critique(verdict="PASS", gaps=[], reasoning="Looks good")
    mock_get_llm.return_value = mock_llm_response(mock_critique)

    state = {"query": "test query", "summaries": []}
    result = await critic_node(state)

    assert result["critique"].verdict == "PASS"


@pytest.mark.asyncio
@patch("research_agent.graph.nodes.critic.get_llm")
async def test_critic_node_force_fail_on_retry_limit(mock_get_llm, mock_llm_response):
    # LLM wants to REVISE, but retry_count is 3 (max)
    mock_critique = Critique(verdict="REVISE", gaps=["gap"], refined_query="q", reasoning="Need more")
    mock_get_llm.return_value = mock_llm_response(mock_critique)

    state = {"query": "test query", "retry_count": 3}
    result = await critic_node(state)

    # Should be forced to FAIL
    assert result["critique"].verdict == "FAIL"


def test_route_after_critic():
    assert route_after_critic({"critique": Critique(verdict="PASS", gaps=[], reasoning="")}) == "report_node"
    assert route_after_critic({"critique": Critique(verdict="REVISE", gaps=[], reasoning="", refined_query="q")}) == "planner_node"
    assert route_after_critic({"critique": Critique(verdict="FAIL", gaps=[], reasoning="")}) == "error_handler_node"


# ── Error Handler Node Tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_error_handler_node():
    state = {
        "query": "test query",
        "error_log": [
            AgentError(node_name="test", error_type="ValueError", message="test", recoverable=False)
        ]
    }
    result = await error_handler_node(state)

    assert "final_report" in result
    report = result["final_report"]
    assert report.quality_score == 0.0
    assert len(report.sections) == 1
    assert "Pipeline Errors" in report.sections[0].heading
