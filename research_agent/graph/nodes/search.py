"""
Search node — parallel web search via LangGraph Send() fan-out.

Each search worker processes a single subtask: it runs Tavily search
for each of the subtask's search queries, falls back to Wikipedia
when Tavily returns < 2 results, and scores relevance with a cosine
similarity check against the original query embedding.

Architecture:
- ``fan_out_to_search()`` — conditional edge function that creates
  one ``Send("search_worker", ...)`` per subtask.
- ``search_worker_node()`` — processes a single subtask (receives
  ``SearchWorkerInput`` from Send).
- ``aggregate_search_node()`` — no-op sync barrier where all parallel
  workers converge before summarizer fan-out.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langgraph.types import Send

from research_agent.graph.state import AgentState, SearchWorkerInput
from research_agent.models.schemas import AgentError, SearchResult, SubTask
from research_agent.tools.tavily_tool import tavily_search
from research_agent.tools.wikipedia_tool import wikipedia_search

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "models/embedding-001"


# ── Cosine similarity (no numpy dependency) ─────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Fan-out function (conditional edge) ─────────────────────────────────────


def fan_out_to_search(state: AgentState) -> list[Send]:
    """Create one ``Send("search_worker", ...)`` per subtask.

    Called as a conditional edge after ``planner_node``.
    """
    plan = state.get("plan")
    if not plan or not plan.subtasks:
        logger.error("fan_out_to_search: no plan/subtasks in state.")
        return [Send("error_handler_node", state)]

    query = state["query"]

    sends = [
        Send(
            "search_worker",
            SearchWorkerInput(
                subtask=subtask.model_dump(),
                query=query,
            ),
        )
        for subtask in plan.subtasks
    ]
    logger.info("fan_out_to_search: dispatching %d search workers.", len(sends))
    return sends


# ── Search worker node (runs per-subtask via Send) ──────────────────────────


async def search_worker_node(state: SearchWorkerInput) -> dict[str, Any]:
    """Execute searches for a single subtask.

    Steps:
    1. Run Tavily search for each search_query (with 10 s timeout).
    2. If Tavily returns < 2 results for a query, fall back to Wikipedia.
    3. Embed the original query and each result's content, compute
       cosine similarity as a relevance score.
    4. Return ``SearchResult`` objects (merged into main state via reducer).
    """
    start = time.perf_counter()

    subtask = SubTask.model_validate(state["subtask"])
    query = state["query"]

    errors: list[AgentError] = []
    raw_results: list[dict] = []

    # ── 1. Run searches ─────────────────────────────────────────────────
    for search_query in subtask.search_queries:
        try:
            tavily_results = await tavily_search(search_query)
        except Exception as e:
            logger.warning("Tavily error for '%s': %s", search_query, e)
            tavily_results = []
            errors.append(
                AgentError(
                    node_name="search_worker",
                    error_type=type(e).__name__,
                    message=f"Tavily failed for '{search_query}': {e}",
                    recoverable=True,
                )
            )

        # Fallback to Wikipedia if Tavily returned < 2 results
        if len(tavily_results) < 2:
            logger.info(
                "Tavily returned %d result(s) for '%s' — falling back to Wikipedia.",
                len(tavily_results),
                search_query,
            )
            try:
                wiki_results = await wikipedia_search(search_query)
                tavily_results.extend(wiki_results)
            except Exception as e:
                logger.warning("Wikipedia fallback failed: %s", e)
                errors.append(
                    AgentError(
                        node_name="search_worker",
                        error_type=type(e).__name__,
                        message=f"Wikipedia fallback failed for '{search_query}': {e}",
                        recoverable=True,
                    )
                )

        raw_results.extend(tavily_results)

    # ── 2. Score relevance via embeddings ───────────────────────────────
    search_results: list[SearchResult] = []

    if raw_results:
        try:
            embeddings = GoogleGenerativeAIEmbeddings(
                model=_EMBEDDING_MODEL,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
            )
            query_vec = await embeddings.aembed_query(query)

            contents = [r.get("content", "")[:1000] for r in raw_results]
            content_vecs = await embeddings.aembed_documents(contents)

            for raw, content_vec in zip(raw_results, content_vecs):
                relevance = _cosine_similarity(query_vec, content_vec)
                search_results.append(
                    SearchResult(
                        subtask_id=subtask.id,
                        source_url=raw.get("url", ""),
                        title=raw.get("title", ""),
                        content=raw.get("content", "")[:3000],
                        relevance_score=round(max(0.0, min(1.0, relevance)), 4),
                    )
                )
        except Exception as e:
            logger.warning(
                "Embedding scoring failed — using raw scores: %s", e
            )
            for raw in raw_results:
                search_results.append(
                    SearchResult(
                        subtask_id=subtask.id,
                        source_url=raw.get("url", ""),
                        title=raw.get("title", ""),
                        content=raw.get("content", "")[:3000],
                        relevance_score=round(raw.get("score", 0.5), 4),
                    )
                )

    # Sort by relevance (highest first)
    search_results.sort(key=lambda r: r.relevance_score, reverse=True)

    latency = round(time.perf_counter() - start, 3)
    logger.info(
        "search_worker[%s]: %d results in %.3fs",
        subtask.id,
        len(search_results),
        latency,
    )

    return {
        "search_results": search_results,
        "error_log": errors,
        "metadata": {f"search_{subtask.id}_latency_s": latency},
    }


# ── Aggregate (sync barrier) ───────────────────────────────────────────────


async def aggregate_search_node(state: AgentState) -> dict[str, Any]:
    """No-op sync barrier where parallel search workers converge.

    After all ``search_worker`` instances complete and their results
    are merged via the ``operator.add`` reducer, this node runs once
    with the fully merged state. Its only purpose is to provide a
    stable edge target for the summarizer fan-out.
    """
    result_count = len(state.get("search_results", []))
    logger.info("aggregate_search: %d total search results collected.", result_count)
    return {"metadata": {"total_search_results": result_count}}
