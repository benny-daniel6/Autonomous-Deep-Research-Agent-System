"""
Shared LangGraph state definition for the research agent pipeline.

AgentState is the single TypedDict that flows through every node in the graph.
LangGraph manages state immutably — each node receives the current state and
returns a partial dict of updates. Reducer annotations control how list fields
are merged (append semantics via ``operator.add``) and how the metadata dict
is merged (shallow dict merge via ``_merge_dicts``).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

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


# ── Custom reducers ─────────────────────────────────────────────────────────


def _merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer that shallow-merges metadata dicts.

    Right-side values overwrite left-side values on key conflict.
    This lets multiple nodes contribute latency metrics without
    clobbering each other.
    """
    if not left:
        return right or {}
    if not right:
        return left
    return {**left, **right}


# ── Main graph state ────────────────────────────────────────────────────────


class AgentState(TypedDict, total=False):
    """Shared state flowing through all LangGraph nodes.

    Fields use ``Annotated[..., operator.add]`` where list-append
    semantics are needed — LangGraph's built-in reducer will
    concatenate lists returned by parallel nodes (e.g. search, summarizer)
    instead of overwriting them.

    ``metadata`` uses a custom shallow-merge reducer so every node can
    independently write latency metrics without overwriting others.

    Fields without a reducer annotation are overwritten on each update
    (standard last-write-wins behaviour).
    """

    # ── Input ───────────────────────────────────────────────────────────
    query: str

    # ── Planner output ──────────────────────────────────────────────────
    plan: Plan

    # ── Search outputs (appended via parallel Send()) ───────────────────
    search_results: Annotated[list[SearchResult], operator.add]

    # ── Summarizer outputs (appended via parallel Send()) ───────────────
    summaries: Annotated[list[Summary], operator.add]

    # ── Critic output ───────────────────────────────────────────────────
    critique: Critique

    # ── Report output ───────────────────────────────────────────────────
    final_report: Report

    # ── Memory ──────────────────────────────────────────────────────────
    memory_hits: Annotated[list[MemoryHit], operator.add]

    # ── Error handling ──────────────────────────────────────────────────
    error_log: Annotated[list[AgentError], operator.add]
    retry_count: int

    # ── Observability ───────────────────────────────────────────────────
    # Shallow-merge reducer so each node can write its own latency key
    # (e.g. "planner_latency_s", "search_latency_s") independently.
    metadata: Annotated[dict[str, Any], _merge_dicts]


# ── Worker input types for Send() fan-out ───────────────────────────────────
# These are NOT part of AgentState. They define the shape of the dict
# passed to parallel worker nodes via LangGraph's Send() API.


class SearchWorkerInput(TypedDict):
    """Input sent to each parallel search worker via ``Send()``."""

    subtask: dict       # SubTask.model_dump()
    query: str          # original research query


class SummarizerWorkerInput(TypedDict):
    """Input sent to each parallel summarizer worker via ``Send()``."""

    subtask_id: str
    subtask_description: str
    subtask_search_results: list[dict]  # list of SearchResult.model_dump()
    query: str                          # original research query
