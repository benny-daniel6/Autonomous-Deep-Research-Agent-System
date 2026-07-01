"""
Report nodes — compile the final research report and handle cached reports.

Two nodes live here:

- ``report_node`` — assembles a structured ``Report`` from summaries,
  computes a quality score, stores the report in ChromaDB for future
  memory retrieval, and logs total pipeline latency.

- ``report_from_memory_node`` — formats a previously cached report
  retrieved by the memory check, adding a "retrieved from memory" note.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from research_agent.graph.nodes import get_llm
from research_agent.graph.state import AgentState
from research_agent.memory.chroma_store import get_memory_store
from research_agent.models.schemas import AgentError, Report, ReportSection

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
You are a research report compiler. Given a set of subtask summaries,
produce a polished, well-structured research report.

Rules:
- Create a clear, descriptive title for the report.
- Organise the report into logical sections with headings.
- Each section should synthesise information from relevant summaries.
- Include inline citations as [Source: URL] where appropriate.
- List ALL unique source URLs in the "supporting_sources" field of
  each section and in the top-level "citations" list.
- Maintain an academic but accessible tone.
- Do NOT invent information — only use what the summaries provide.
"""


async def report_node(state: AgentState) -> dict[str, Any]:
    """Compile the final research report from summaries.

    Calculates ``quality_score`` as::

        avg(summary confidences) * critic_adjustment_factor

    where ``critic_adjustment_factor`` is 1.0 for PASS, 0.8 for REVISE
    (meaning the report was produced after at least one retry).

    Stores the completed report in ChromaDB for future retrieval.
    """
    start = time.perf_counter()

    query = state["query"]
    summaries = state.get("summaries", [])
    critique = state.get("critique")
    plan = state.get("plan")

    errors: list[AgentError] = []

    # ── Compute quality score ───────────────────────────────────────────
    if summaries:
        avg_confidence = sum(s.confidence for s in summaries) / len(summaries)
    else:
        avg_confidence = 0.0

    critic_adjustment = 1.0
    if critique and critique.verdict != "PASS":
        critic_adjustment = 0.8

    quality_score = round(avg_confidence * critic_adjustment, 4)

    # ── Build LLM prompt ───────────────────────────────────────────────
    summaries_text = ""
    all_sources: list[str] = []
    for s in summaries:
        summaries_text += (
            f"\n--- Subtask: {s.subtask_id} (confidence: {s.confidence:.2f}) ---\n"
            f"{s.summary_text}\n"
            f"Sources: {', '.join(s.sources)}\n"
        )
        all_sources.extend(s.sources)

    unique_sources = list(dict.fromkeys(all_sources))  # preserve order

    user_prompt = (
        f"Research query: {query}\n\n"
        f"Subtask summaries:\n{summaries_text}\n\n"
        f"Produce a comprehensive research report."
    )

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    llm = get_llm(temperature=0.2).with_structured_output(Report)

    try:
        report: Report = await llm.ainvoke(messages)
        # Override quality_score with our computed value
        report.quality_score = quality_score
        # Ensure citations include all sources
        report.citations = unique_sources or report.citations
    except Exception as first_err:
        logger.warning("report_node: first attempt failed (%s), retrying…", first_err)
        messages.append(
            HumanMessage(
                content=(
                    "Your response was invalid. Return ONLY valid JSON "
                    "matching the Report schema."
                )
            )
        )
        try:
            report = await llm.ainvoke(messages)
            report.quality_score = quality_score
            report.citations = unique_sources or report.citations
        except Exception as second_err:
            latency = round(time.perf_counter() - start, 3)
            logger.error("report_node: both attempts failed: %s", second_err)

            # Build a minimal fallback report from summaries
            fallback_sections = [
                ReportSection(
                    heading=f"Summary — {s.subtask_id}",
                    content=s.summary_text,
                    supporting_sources=s.sources,
                )
                for s in summaries
            ]

            report = Report(
                title=f"Research Report: {query}",
                sections=fallback_sections or [
                    ReportSection(
                        heading="Error",
                        content="Report generation failed.",
                        supporting_sources=[],
                    )
                ],
                citations=unique_sources,
                quality_score=quality_score,
            )
            errors.append(
                AgentError(
                    node_name="report_node",
                    error_type=type(second_err).__name__,
                    message=str(second_err),
                    recoverable=False,
                )
            )

    # ── Store in ChromaDB ──────────────────────────────────────────────
    try:
        store = get_memory_store()
        await asyncio.to_thread(store.store, query, report)
    except Exception as e:
        logger.error("report_node: failed to store report in memory: %s", e)
        errors.append(
            AgentError(
                node_name="report_node",
                error_type=type(e).__name__,
                message=f"Failed to cache report: {e}",
                recoverable=True,
            )
        )

    latency = round(time.perf_counter() - start, 3)
    logger.info(
        "report_node: '%s' (quality=%.2f, %.3fs)",
        report.title,
        report.quality_score,
        latency,
    )

    return {
        "final_report": report,
        "error_log": errors,
        "metadata": {
            "report_latency_s": latency,
            "quality_score": report.quality_score,
        },
    }


async def report_from_memory_node(state: AgentState) -> dict[str, Any]:
    """Format a cached report retrieved from ChromaDB memory.

    Adds a note indicating the report was retrieved from memory
    along with the similarity score.
    """
    start = time.perf_counter()

    memory_hits = state.get("memory_hits", [])
    errors: list[AgentError] = []

    if not memory_hits:
        latency = round(time.perf_counter() - start, 3)
        return {
            "final_report": Report(
                title="Error: No Memory Hit",
                sections=[
                    ReportSection(
                        heading="Error",
                        content="Routed to memory report but no hits found.",
                        supporting_sources=[],
                    )
                ],
                citations=[],
                quality_score=0.0,
            ),
            "error_log": [
                AgentError(
                    node_name="report_from_memory_node",
                    error_type="NoMemoryHit",
                    message="No memory hits available.",
                    recoverable=False,
                )
            ],
            "metadata": {"report_from_memory_latency_s": latency},
        }

    best_hit = memory_hits[0]

    # Attempt to reconstruct the full report from ChromaDB
    try:
        store = get_memory_store()
        cached_report = await asyncio.to_thread(
            store.get_report_from_hit, best_hit
        )
    except Exception as e:
        logger.error("report_from_memory_node: reconstruction failed: %s", e)
        cached_report = None
        errors.append(
            AgentError(
                node_name="report_from_memory_node",
                error_type=type(e).__name__,
                message=str(e),
                recoverable=False,
            )
        )

    if cached_report:
        # Prepend a "retrieved from memory" note to the first section
        memory_note = (
            f"> **Retrieved from memory** "
            f"(similarity: {best_hit.similarity_score * 100:.1f}%)\n\n"
        )
        if cached_report.sections:
            cached_report.sections[0].content = (
                memory_note + cached_report.sections[0].content
            )

        report = cached_report
    else:
        # Fallback: create a minimal report from the summary
        report = Report(
            title="Cached Research Report",
            sections=[
                ReportSection(
                    heading="Summary (from memory)",
                    content=(
                        f"> Retrieved from memory "
                        f"(similarity: {best_hit.similarity_score * 100:.1f}%)\n\n"
                        f"{best_hit.report_summary}"
                    ),
                    supporting_sources=[],
                )
            ],
            citations=[],
            quality_score=best_hit.similarity_score,
        )

    latency = round(time.perf_counter() - start, 3)
    logger.info(
        "report_from_memory_node: similarity=%.4f (%.3fs)",
        best_hit.similarity_score,
        latency,
    )

    return {
        "final_report": report,
        "error_log": errors,
        "metadata": {"report_from_memory_latency_s": latency},
    }
