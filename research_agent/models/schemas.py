"""
Pydantic v2 models for the Multi-Agent Research System.

Every structured output in the pipeline flows through these models.
All LLM calls use `.with_structured_output()` bound to one of these schemas —
zero free-form parsing anywhere in the system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# ── Planner models ──────────────────────────────────────────────────────────


class SubTask(BaseModel):
    """A single research subtask produced by the Planner agent.

    Each subtask represents a focused angle on the user's query
    with pre-generated search queries ready for the Search agent.
    """

    id: str = Field(
        ...,
        description="Unique identifier for this subtask (e.g. 'subtask_1').",
    )
    description: str = Field(
        ...,
        description="What this subtask investigates.",
    )
    search_queries: list[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="2-3 specific search queries for the Search agent.",
    )
    priority: int = Field(
        ...,
        ge=1,
        le=5,
        description="Priority ranking (1 = highest, 5 = lowest).",
    )


class Plan(BaseModel):
    """The full research plan output by the Planner agent.

    Contains 2-4 subtasks with a reasoning trace explaining
    why these subtasks cover the user's query.
    """

    subtasks: list[SubTask] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="Ordered list of 2-4 focused research subtasks.",
    )
    reasoning: str = Field(
        ...,
        description="Brief explanation of the decomposition strategy.",
    )


# ── Search models ───────────────────────────────────────────────────────────


class SearchResult(BaseModel):
    """A single search result tied to a subtask.

    Produced by the Search agent from Tavily or Wikipedia.
    """

    subtask_id: str = Field(
        ...,
        description="ID of the subtask this result belongs to.",
    )
    source_url: str = Field(
        ...,
        description="URL of the source page.",
    )
    title: str = Field(
        ...,
        description="Title of the source page.",
    )
    content: str = Field(
        ...,
        description="Extracted text content from the source.",
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity relevance score (0.0-1.0).",
    )


# ── Summarizer models ──────────────────────────────────────────────────────


class Summary(BaseModel):
    """A per-subtask summary produced by the Summarizer agent.

    Includes a confidence score so the Critic knows which
    subtasks might need additional research.
    """

    subtask_id: str = Field(
        ...,
        description="ID of the subtask being summarized.",
    )
    summary_text: str = Field(
        ...,
        description="Synthesized summary of search results for this subtask.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence score (0.0-1.0) based on source quality "
            "and cross-source consistency."
        ),
    )
    sources: list[str] = Field(
        default_factory=list,
        description="URLs of sources used in this summary.",
    )


# ── Critic models ──────────────────────────────────────────────────────────


class Critique(BaseModel):
    """The Critic agent's evaluation of the collected summaries.

    Determines whether the research is complete (PASS),
    needs refinement (REVISE), or has irrecoverably failed (FAIL).
    """

    verdict: Literal["PASS", "REVISE", "FAIL"] = Field(
        ...,
        description="Overall verdict: PASS, REVISE, or FAIL.",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Identified gaps or weaknesses in the research.",
    )
    refined_query: str | None = Field(
        default=None,
        description=(
            "Refined search query to address gaps. "
            "Required when verdict is REVISE."
        ),
    )
    reasoning: str = Field(
        ...,
        description="Detailed justification for the verdict.",
    )


# ── Report models ──────────────────────────────────────────────────────────


class ReportSection(BaseModel):
    """A single section within the final research report."""

    heading: str = Field(
        ...,
        description="Section heading.",
    )
    content: str = Field(
        ...,
        description="Section body text (markdown).",
    )
    supporting_sources: list[str] = Field(
        default_factory=list,
        description="URLs of sources that support this section.",
    )


class Report(BaseModel):
    """The final research report produced by the Report agent.

    Includes citations, a quality score, and a generation timestamp
    so it can be cached in ChromaDB for future memory retrieval.
    """

    title: str = Field(
        ...,
        description="Report title.",
    )
    sections: list[ReportSection] = Field(
        ...,
        min_length=1,
        description="Ordered sections of the report.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="All unique source URLs cited in the report.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of report generation.",
    )
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Overall quality score: avg(summary confidences) "
            "* critic adjustment factor."
        ),
    )


# ── Error & memory models ──────────────────────────────────────────────────


class AgentError(BaseModel):
    """Structured error logged by any node during pipeline execution.

    Every exception in the system gets captured here instead of
    being silently swallowed.
    """

    node_name: str = Field(
        ...,
        description="Name of the graph node that raised the error.",
    )
    error_type: str = Field(
        ...,
        description="Exception class name (e.g. 'TimeoutError').",
    )
    message: str = Field(
        ...,
        description="Human-readable error message.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the error occurred.",
    )
    recoverable: bool = Field(
        ...,
        description="Whether the pipeline can continue after this error.",
    )


class MemoryHit(BaseModel):
    """A cached report retrieved from ChromaDB semantic memory.

    When a user's query closely matches a previously completed
    research report, we skip re-running the full pipeline.
    """

    query: str = Field(
        ...,
        description="The original query that produced the cached report.",
    )
    report_summary: str = Field(
        ...,
        description="Summary of the cached report.",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cosine similarity between the current and cached query.",
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of retrieval.",
    )
