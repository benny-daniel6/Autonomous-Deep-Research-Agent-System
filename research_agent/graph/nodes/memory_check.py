"""
Memory check node — first node in the pipeline.

Embeds the incoming query and checks ChromaDB for semantically
similar past research reports (cosine similarity > 0.85).

If a hit is found, the graph routes to ``report_from_memory_node``
to serve the cached result. Otherwise, it routes to ``planner_node``
to start fresh research.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from research_agent.graph.state import AgentState
from research_agent.memory.chroma_store import get_memory_store
from research_agent.models.schemas import AgentError

logger = logging.getLogger(__name__)


async def memory_check_node(state: AgentState) -> dict[str, Any]:
    """Query ChromaDB for similar past reports.

    On ChromaDB connection errors, the node logs a recoverable
    ``AgentError`` and returns empty ``memory_hits`` so the pipeline
    falls through to the planner instead of crashing.
    """
    start = time.perf_counter()
    query = state["query"]

    try:
        store = get_memory_store()
        hits = await asyncio.to_thread(store.query, query)
        latency = round(time.perf_counter() - start, 3)

        logger.info(
            "memory_check_node: %d hit(s) for '%s' (%.3fs)",
            len(hits),
            query,
            latency,
        )

        return {
            "memory_hits": hits,
            "metadata": {"memory_check_latency_s": latency},
        }

    except Exception as e:
        latency = round(time.perf_counter() - start, 3)
        logger.error("memory_check_node failed: %s", e)

        error = AgentError(
            node_name="memory_check_node",
            error_type=type(e).__name__,
            message=f"ChromaDB error — skipping memory check: {e}",
            recoverable=True,
        )

        return {
            "memory_hits": [],
            "error_log": [error],
            "metadata": {"memory_check_latency_s": latency},
        }


def route_after_memory_check(state: AgentState) -> str:
    """Conditional edge: route to cached report or fresh planning.

    Returns:
        ``"report_from_memory_node"`` if a high-confidence memory hit
        exists, otherwise ``"planner_node"``.
    """
    hits = state.get("memory_hits", [])
    if hits:
        logger.info(
            "Memory hit found (similarity=%.4f) — routing to cache.",
            hits[0].similarity_score,
        )
        return "report_from_memory_node"

    return "planner_node"
