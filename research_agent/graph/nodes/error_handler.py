"""
Error handler node — terminal node for irrecoverable failures.

Produces a partial report summarising what went wrong and any
partial results that were collected before the failure. This
ensures the pipeline never returns nothing — even in a catastrophic
failure, the user gets a structured response explaining the issue.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from research_agent.graph.state import AgentState
from research_agent.models.schemas import Report, ReportSection

logger = logging.getLogger(__name__)


async def error_handler_node(state: AgentState) -> dict[str, Any]:
    """Build a partial report from whatever data is available.

    Includes:
    - An error summary section listing all logged errors.
    - Any partial summaries that were successfully generated.
    - A quality_score of 0.0 to clearly flag this as a failed report.
    """
    start = time.perf_counter()

    query = state.get("query", "Unknown query")
    error_log = state.get("error_log", [])
    summaries = state.get("summaries", [])
    critique = state.get("critique")

    sections: list[ReportSection] = []

    # ── Error summary section ──────────────────────────────────────────
    error_lines = []
    for err in error_log:
        error_lines.append(
            f"- **[{err.node_name}]** `{err.error_type}`: {err.message} "
            f"(recoverable={err.recoverable})"
        )

    error_text = "\n".join(error_lines) if error_lines else "No errors logged."

    sections.append(
        ReportSection(
            heading="Pipeline Errors",
            content=(
                "The research pipeline encountered irrecoverable errors "
                "and could not produce a complete report.\n\n"
                f"{error_text}"
            ),
            supporting_sources=[],
        )
    )

    # ── Critic feedback (if available) ──────────────────────────────────
    if critique:
        sections.append(
            ReportSection(
                heading="Critic Feedback",
                content=(
                    f"**Verdict:** {critique.verdict}\n\n"
                    f"**Reasoning:** {critique.reasoning}\n\n"
                    f"**Gaps:** {', '.join(critique.gaps) if critique.gaps else 'None'}"
                ),
                supporting_sources=[],
            )
        )

    # ── Partial results (if any summaries were generated) ──────────────
    if summaries:
        for s in summaries:
            sections.append(
                ReportSection(
                    heading=f"Partial Summary — {s.subtask_id}",
                    content=(
                        f"*(confidence: {s.confidence:.2f})*\n\n"
                        f"{s.summary_text}"
                    ),
                    supporting_sources=s.sources,
                )
            )

    report = Report(
        title=f"Partial Report: {query}",
        sections=sections,
        citations=[],
        quality_score=0.0,
    )

    latency = round(time.perf_counter() - start, 3)
    logger.info(
        "error_handler_node: produced partial report with %d section(s) (%.3fs)",
        len(sections),
        latency,
    )

    return {
        "final_report": report,
        "metadata": {"error_handler_latency_s": latency},
    }
