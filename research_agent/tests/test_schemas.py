"""
Tests for Pydantic schema validation (Phase 1).

Verifies that all models enforce field constraints, defaults,
serialisation round-trips, and reject invalid data cleanly.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from research_agent.models.schemas import (
    AgentError,
    Critique,
    MemoryHit,
    Plan,
    Report,
    ReportSection,
    SearchResult,
    SubTask,
    Summary,
)


# ── SubTask ─────────────────────────────────────────────────────────────────


class TestSubTask:
    def test_valid_subtask(self) -> None:
        st = SubTask(
            id="subtask_1",
            description="Investigate CRISPR mechanisms",
            search_queries=["CRISPR Cas9 mechanism", "CRISPR gene editing"],
            priority=1,
        )
        assert st.id == "subtask_1"
        assert len(st.search_queries) == 2
        assert st.priority == 1

    def test_rejects_too_few_search_queries(self) -> None:
        with pytest.raises(ValidationError, match="search_queries"):
            SubTask(
                id="subtask_1",
                description="Test",
                search_queries=["only one"],
                priority=1,
            )

    def test_rejects_too_many_search_queries(self) -> None:
        with pytest.raises(ValidationError, match="search_queries"):
            SubTask(
                id="subtask_1",
                description="Test",
                search_queries=["a", "b", "c", "d"],
                priority=1,
            )

    def test_rejects_priority_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="priority"):
            SubTask(
                id="subtask_1",
                description="Test",
                search_queries=["a", "b"],
                priority=0,
            )
        with pytest.raises(ValidationError, match="priority"):
            SubTask(
                id="subtask_1",
                description="Test",
                search_queries=["a", "b"],
                priority=6,
            )


# ── Plan ────────────────────────────────────────────────────────────────────


class TestPlan:
    def _make_subtask(self, idx: int = 1) -> SubTask:
        return SubTask(
            id=f"subtask_{idx}",
            description=f"Task {idx}",
            search_queries=["q1", "q2"],
            priority=idx,
        )

    def test_valid_plan(self) -> None:
        plan = Plan(
            subtasks=[self._make_subtask(1), self._make_subtask(2)],
            reasoning="Decomposed into two angles.",
        )
        assert len(plan.subtasks) == 2

    def test_rejects_fewer_than_two_subtasks(self) -> None:
        with pytest.raises(ValidationError, match="subtasks"):
            Plan(
                subtasks=[self._make_subtask(1)],
                reasoning="Only one.",
            )

    def test_rejects_more_than_four_subtasks(self) -> None:
        with pytest.raises(ValidationError, match="subtasks"):
            Plan(
                subtasks=[self._make_subtask(i) for i in range(1, 6)],
                reasoning="Too many.",
            )


# ── SearchResult ────────────────────────────────────────────────────────────


class TestSearchResult:
    def test_valid_search_result(self) -> None:
        sr = SearchResult(
            subtask_id="subtask_1",
            source_url="https://example.com",
            title="Example",
            content="Some content",
            relevance_score=0.92,
        )
        assert sr.relevance_score == 0.92

    def test_rejects_relevance_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="relevance_score"):
            SearchResult(
                subtask_id="subtask_1",
                source_url="https://example.com",
                title="Example",
                content="Content",
                relevance_score=1.5,
            )


# ── Summary ─────────────────────────────────────────────────────────────────


class TestSummary:
    def test_valid_summary(self) -> None:
        s = Summary(
            subtask_id="subtask_1",
            summary_text="CRISPR is a gene editing tool.",
            confidence=0.85,
            sources=["https://a.com", "https://b.com"],
        )
        assert s.confidence == 0.85
        assert len(s.sources) == 2

    def test_defaults_sources_to_empty(self) -> None:
        s = Summary(
            subtask_id="subtask_1",
            summary_text="Summary",
            confidence=0.7,
        )
        assert s.sources == []


# ── Critique ────────────────────────────────────────────────────────────────


class TestCritique:
    def test_pass_verdict(self) -> None:
        c = Critique(
            verdict="PASS",
            gaps=[],
            reasoning="All subtasks covered.",
        )
        assert c.verdict == "PASS"
        assert c.refined_query is None

    def test_revise_verdict(self) -> None:
        c = Critique(
            verdict="REVISE",
            gaps=["Missing recent data"],
            refined_query="CRISPR 2024 developments",
            reasoning="Need more recent sources.",
        )
        assert c.verdict == "REVISE"
        assert c.refined_query is not None

    def test_rejects_invalid_verdict(self) -> None:
        with pytest.raises(ValidationError, match="verdict"):
            Critique(
                verdict="MAYBE",  # type: ignore[arg-type]
                reasoning="Not a valid verdict.",
            )


# ── Report ──────────────────────────────────────────────────────────────────


class TestReport:
    def test_valid_report(self) -> None:
        r = Report(
            title="CRISPR Research Report",
            sections=[
                ReportSection(
                    heading="Introduction",
                    content="CRISPR overview.",
                    supporting_sources=["https://a.com"],
                )
            ],
            citations=["https://a.com"],
            quality_score=0.88,
        )
        assert r.quality_score == 0.88
        assert isinstance(r.generated_at, datetime)

    def test_json_round_trip(self) -> None:
        r = Report(
            title="Test",
            sections=[
                ReportSection(heading="S1", content="C1", supporting_sources=[])
            ],
            citations=[],
            quality_score=0.5,
        )
        json_str = r.model_dump_json()
        r2 = Report.model_validate_json(json_str)
        assert r2.title == r.title
        assert r2.quality_score == r.quality_score


# ── AgentError ──────────────────────────────────────────────────────────────


class TestAgentError:
    def test_valid_error(self) -> None:
        e = AgentError(
            node_name="search_node",
            error_type="TimeoutError",
            message="Tavily timed out after 10s",
            recoverable=True,
        )
        assert e.recoverable is True
        assert isinstance(e.timestamp, datetime)


# ── MemoryHit ───────────────────────────────────────────────────────────────


class TestMemoryHit:
    def test_valid_memory_hit(self) -> None:
        m = MemoryHit(
            query="How does CRISPR work?",
            report_summary="Title: CRISPR Report\nQuality: 0.90",
            similarity_score=0.92,
        )
        assert m.similarity_score == 0.92
        assert isinstance(m.retrieved_at, datetime)

    def test_rejects_similarity_above_one(self) -> None:
        with pytest.raises(ValidationError, match="similarity_score"):
            MemoryHit(
                query="test",
                report_summary="test",
                similarity_score=1.1,
            )
