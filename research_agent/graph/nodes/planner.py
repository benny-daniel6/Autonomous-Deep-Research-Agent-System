"""
Planner node — decomposes the research query into focused subtasks.

Uses ``ChatGoogleGenerativeAI.with_structured_output(Plan)`` so the
LLM is forced to return a valid ``Plan`` Pydantic model (2-4 subtasks,
each with 2-3 search queries). Zero free-form text parsing.

On retry (when ``Critique.verdict == "REVISE"``), the planner
incorporates the critic's feedback and refined query into its prompt,
and increments ``retry_count``.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from research_agent.graph.nodes import get_llm
from research_agent.graph.state import AgentState
from research_agent.models.schemas import AgentError, Plan

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a research planner. Your job is to break a research query into 2-4
focused subtasks. Each subtask must have 2-3 specific search queries that
will be sent to a web search engine.

Rules:
- Return ONLY valid JSON matching the Plan schema.
- Each subtask must investigate a distinct angle of the query.
- Search queries must be specific and diverse (not rephrased duplicates).
- Assign priority 1 (highest) to the most important subtask.
- Keep the reasoning field concise (1-2 sentences).
"""

_RETRY_ADDENDUM = """\

IMPORTANT — RETRY CONTEXT:
A previous research attempt was critiqued. The critic's feedback:
  Gaps: {gaps}
  Refined query: {refined_query}

Incorporate this feedback. Focus on addressing the identified gaps.
You may reuse subtasks that were adequate, but add or modify subtasks
to cover the gaps.
"""


async def planner_node(state: AgentState) -> dict[str, Any]:
    """Generate a research plan from the user's query.

    Returns a partial state dict with:
    - ``plan``: the structured ``Plan`` object
    - ``retry_count``: incremented if this is a retry
    - ``metadata``: planner latency
    - ``error_log``: populated on failure
    """
    start = time.perf_counter()
    query = state["query"]
    critique = state.get("critique")
    retry_count = state.get("retry_count", 0)

    # ── Build prompt ────────────────────────────────────────────────────
    system_text = _SYSTEM_PROMPT
    if critique and critique.verdict == "REVISE":
        system_text += _RETRY_ADDENDUM.format(
            gaps=", ".join(critique.gaps) if critique.gaps else "none specified",
            refined_query=critique.refined_query or query,
        )
        retry_count += 1

    messages = [
        SystemMessage(content=system_text),
        HumanMessage(content=f"Research query: {query}"),
    ]

    # ── Invoke LLM with structured output ───────────────────────────────
    llm = get_llm(temperature=0.0).with_structured_output(Plan)

    try:
        plan: Plan = await llm.ainvoke(messages)
    except Exception as first_err:
        # Retry once with stricter prompt
        logger.warning(
            "planner_node: first attempt failed (%s), retrying…", first_err
        )
        messages.append(
            HumanMessage(
                content=(
                    "Your previous response was invalid. "
                    "Return ONLY a JSON object matching the Plan schema. "
                    "No markdown, no commentary."
                )
            )
        )
        try:
            plan = await llm.ainvoke(messages)
        except Exception as second_err:
            latency = round(time.perf_counter() - start, 3)
            logger.error("planner_node: both attempts failed: %s", second_err)
            return {
                "retry_count": retry_count,
                "error_log": [
                    AgentError(
                        node_name="planner_node",
                        error_type=type(second_err).__name__,
                        message=str(second_err),
                        recoverable=False,
                    )
                ],
                "metadata": {"planner_latency_s": latency},
            }

    latency = round(time.perf_counter() - start, 3)
    logger.info(
        "planner_node: created %d subtask(s) in %.3fs",
        len(plan.subtasks),
        latency,
    )

    return {
        "plan": plan,
        "retry_count": retry_count,
        "metadata": {"planner_latency_s": latency},
    }
