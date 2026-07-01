"""
Critic node — evaluates research quality and decides next action.

The critic examines all summaries against the original plan and
returns a structured ``Critique`` with one of three verdicts:

- **PASS** → summaries are complete and consistent → proceed to report.
- **REVISE** → gaps identified → include a ``refined_query`` and
  loop back to the planner for re-search (up to 3 retries).
- **FAIL** → irrecoverable quality issue or retry limit reached →
  route to error handler.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from research_agent.graph.nodes import get_llm
from research_agent.graph.state import AgentState
from research_agent.models.schemas import AgentError, Critique

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
You are a research critic. Evaluate the provided summaries against the
original research plan and query.

Check for:
1. Coverage — are ALL subtasks adequately addressed?
2. Contradictions — do any summaries contradict each other?
3. Unsupported claims — are claims backed by cited sources?
4. Depth — is the information sufficiently detailed?

Return a structured Critique with:
- verdict: "PASS" if quality is acceptable, "REVISE" if gaps need
  addressing, "FAIL" if the research is fundamentally flawed.
- gaps: list of specific issues found (empty list if PASS).
- refined_query: a new search query to address gaps (required if REVISE,
  null if PASS or FAIL).
- reasoning: detailed justification for your verdict (2-4 sentences).

Be strict but fair. Minor gaps should be PASS with notes in reasoning.
Only use REVISE for significant missing information.
"""

_MAX_RETRIES = 3


async def critic_node(state: AgentState) -> dict[str, Any]:
    """Evaluate summaries and return a verdict.

    Returns a partial state dict with:
    - ``critique``: the structured ``Critique`` object
    - ``metadata``: critic latency
    - ``error_log``: populated on failure
    """
    start = time.perf_counter()

    query = state["query"]
    plan = state.get("plan")
    summaries = state.get("summaries", [])
    retry_count = state.get("retry_count", 0)

    errors: list[AgentError] = []

    # ── Build context for the critic ────────────────────────────────────
    plan_text = "No plan available."
    if plan:
        plan_parts = []
        for st in plan.subtasks:
            plan_parts.append(
                f"  - [{st.id}] {st.description} (priority={st.priority})"
            )
        plan_text = "\n".join(plan_parts)

    summaries_text = "No summaries available."
    if summaries:
        summary_parts = []
        for s in summaries:
            summary_parts.append(
                f"  - [{s.subtask_id}] confidence={s.confidence:.2f}\n"
                f"    {s.summary_text[:500]}"
            )
        summaries_text = "\n".join(summary_parts)

    user_prompt = (
        f"Original query: {query}\n\n"
        f"Research plan:\n{plan_text}\n\n"
        f"Summaries:\n{summaries_text}\n\n"
        f"Current retry count: {retry_count}/{_MAX_RETRIES}"
    )

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    llm = get_llm(temperature=0.0).with_structured_output(Critique)

    try:
        critique: Critique = await llm.ainvoke(messages)
    except Exception as first_err:
        logger.warning("critic_node: first attempt failed (%s), retrying…", first_err)
        messages.append(
            HumanMessage(
                content=(
                    "Your response was invalid. Return ONLY valid JSON "
                    "matching the Critique schema."
                )
            )
        )
        try:
            critique = await llm.ainvoke(messages)
        except Exception as second_err:
            latency = round(time.perf_counter() - start, 3)
            logger.error("critic_node: both attempts failed: %s", second_err)
            # Default to FAIL on LLM failure
            critique = Critique(
                verdict="FAIL",
                gaps=["Critic LLM evaluation failed."],
                reasoning=f"LLM error: {second_err}",
            )
            errors.append(
                AgentError(
                    node_name="critic_node",
                    error_type=type(second_err).__name__,
                    message=str(second_err),
                    recoverable=False,
                )
            )

    # Force FAIL if retry limit reached and verdict is REVISE
    if critique.verdict == "REVISE" and retry_count >= _MAX_RETRIES:
        logger.warning(
            "critic_node: REVISE verdict but retry_count=%d >= %d — forcing FAIL.",
            retry_count,
            _MAX_RETRIES,
        )
        critique = Critique(
            verdict="FAIL",
            gaps=critique.gaps,
            reasoning=(
                f"Retry limit ({_MAX_RETRIES}) reached. "
                f"Original reasoning: {critique.reasoning}"
            ),
        )

    latency = round(time.perf_counter() - start, 3)
    logger.info(
        "critic_node: verdict=%s (%.3fs)", critique.verdict, latency
    )

    return {
        "critique": critique,
        "error_log": errors,
        "metadata": {"critic_latency_s": latency},
    }


def route_after_critic(state: AgentState) -> str:
    """Conditional edge: route based on critic verdict.

    Returns:
        - ``"report_node"`` on PASS
        - ``"planner_node"`` on REVISE (loops back for re-planning)
        - ``"error_handler_node"`` on FAIL
    """
    critique = state.get("critique")
    if not critique:
        logger.error("route_after_critic: no critique in state — routing to error.")
        return "error_handler_node"

    if critique.verdict == "PASS":
        return "report_node"
    elif critique.verdict == "REVISE":
        return "planner_node"
    else:  # FAIL
        return "error_handler_node"
