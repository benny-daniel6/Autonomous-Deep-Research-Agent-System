"""
Summarizer node — parallel per-subtask summarisation via Send() fan-out.

Each summarizer worker receives one subtask's search results and
produces a ``Summary`` with a confidence score. If confidence < 0.5,
the subtask is flagged for potential re-search.

Architecture:
- ``fan_out_to_summarize()`` — conditional edge function that groups
  search results by subtask_id and creates one
  ``Send("summarizer_worker", ...)`` per subtask.
- ``summarizer_worker_node()`` — summarises a single subtask's results
  using structured LLM output.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send

from research_agent.graph.nodes import get_llm
from research_agent.graph.state import AgentState, SummarizerWorkerInput
from research_agent.models.schemas import AgentError, Summary

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
You are a research summariser. You receive search results for a specific
research subtask and must produce a concise, accurate summary.

Rules:
- Synthesise information across all provided sources.
- Include a confidence score (0.0-1.0) based on:
  * Source quality (authoritative domains score higher)
  * Cross-source consistency (agreement raises confidence)
  * Completeness (are the key aspects of the subtask covered?)
- List all source URLs you referenced in the "sources" field.
- If sources contradict each other, note the disagreement and lower confidence.
- Keep the summary under 500 words.
"""


# ── Fan-out function (conditional edge) ─────────────────────────────────────


def fan_out_to_summarize(state: AgentState) -> list[Send]:
    """Create one ``Send("summarizer_worker", ...)`` per subtask.

    Groups search results by ``subtask_id`` and sends each group
    to a separate summarizer worker.
    """
    plan = state.get("plan")
    search_results = state.get("search_results", [])
    query = state["query"]

    if not plan or not plan.subtasks:
        logger.error("fan_out_to_summarize: no plan in state.")
        return [Send("error_handler_node", state)]

    # Group search results by subtask_id
    results_by_subtask: dict[str, list[dict]] = {}
    for sr in search_results:
        sid = sr.subtask_id
        if sid not in results_by_subtask:
            results_by_subtask[sid] = []
        results_by_subtask[sid].append(sr.model_dump())

    sends: list[Send] = []
    for subtask in plan.subtasks:
        subtask_results = results_by_subtask.get(subtask.id, [])
        sends.append(
            Send(
                "summarizer_worker",
                SummarizerWorkerInput(
                    subtask_id=subtask.id,
                    subtask_description=subtask.description,
                    subtask_search_results=subtask_results,
                    query=query,
                ),
            )
        )

    logger.info(
        "fan_out_to_summarize: dispatching %d summarizer workers.", len(sends)
    )
    return sends


# ── Summarizer worker node ──────────────────────────────────────────────────


async def summarizer_worker_node(
    state: SummarizerWorkerInput,
) -> dict[str, Any]:
    """Summarise search results for a single subtask.

    Uses ``with_structured_output(Summary)`` for zero-parsing
    LLM output. Flags low-confidence subtasks (< 0.5) in error_log.
    """
    start = time.perf_counter()

    subtask_id = state["subtask_id"]
    description = state["subtask_description"]
    results = state["subtask_search_results"]
    query = state["query"]

    errors: list[AgentError] = []

    # Format search results for the LLM
    results_text = ""
    source_urls: list[str] = []
    for i, r in enumerate(results, 1):
        url = r.get("source_url", "")
        source_urls.append(url)
        results_text += (
            f"\n--- Source {i} ---\n"
            f"Title: {r.get('title', 'N/A')}\n"
            f"URL: {url}\n"
            f"Content: {r.get('content', 'N/A')[:2000]}\n"
        )

    if not results_text.strip():
        # No search results to summarise
        latency = round(time.perf_counter() - start, 3)
        summary = Summary(
            subtask_id=subtask_id,
            summary_text=f"No search results available for: {description}",
            confidence=0.0,
            sources=[],
        )
        errors.append(
            AgentError(
                node_name="summarizer_worker",
                error_type="NoResults",
                message=f"No search results for subtask '{subtask_id}'.",
                recoverable=True,
            )
        )
        return {
            "summaries": [summary],
            "error_log": errors,
            "metadata": {f"summarize_{subtask_id}_latency_s": latency},
        }

    user_prompt = (
        f"Research query: {query}\n"
        f"Subtask: {description}\n"
        f"\nSearch results:\n{results_text}"
    )

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    llm = get_llm(temperature=0.0).with_structured_output(Summary)

    try:
        summary: Summary = await llm.ainvoke(messages)
        # Ensure the subtask_id matches (LLM might hallucinate a different one)
        summary.subtask_id = subtask_id
    except Exception as first_err:
        logger.warning(
            "summarizer_worker[%s]: first attempt failed (%s), retrying…",
            subtask_id,
            first_err,
        )
        messages.append(
            HumanMessage(
                content=(
                    "Your response was invalid. Return ONLY valid JSON "
                    "matching the Summary schema."
                )
            )
        )
        try:
            summary = await llm.ainvoke(messages)
            summary.subtask_id = subtask_id
        except Exception as second_err:
            latency = round(time.perf_counter() - start, 3)
            logger.error(
                "summarizer_worker[%s]: both attempts failed.", subtask_id
            )
            summary = Summary(
                subtask_id=subtask_id,
                summary_text=f"Summarisation failed for: {description}",
                confidence=0.0,
                sources=source_urls,
            )
            errors.append(
                AgentError(
                    node_name="summarizer_worker",
                    error_type=type(second_err).__name__,
                    message=str(second_err),
                    recoverable=True,
                )
            )
            return {
                "summaries": [summary],
                "error_log": errors,
                "metadata": {f"summarize_{subtask_id}_latency_s": latency},
            }

    # Flag low-confidence subtasks
    if summary.confidence < 0.5:
        logger.warning(
            "summarizer_worker[%s]: low confidence %.2f — flagging.",
            subtask_id,
            summary.confidence,
        )
        errors.append(
            AgentError(
                node_name="summarizer_worker",
                error_type="LowConfidence",
                message=(
                    f"Subtask '{subtask_id}' has low confidence "
                    f"({summary.confidence:.2f}). May need re-search."
                ),
                recoverable=True,
            )
        )

    latency = round(time.perf_counter() - start, 3)
    logger.info(
        "summarizer_worker[%s]: confidence=%.2f, %.3fs",
        subtask_id,
        summary.confidence,
        latency,
    )

    return {
        "summaries": [summary],
        "error_log": errors,
        "metadata": {f"summarize_{subtask_id}_latency_s": latency},
    }
