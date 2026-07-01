"""
Persistent ChromaDB memory store for caching and retrieving research reports.

Design decisions:
- Uses GoogleGenerativeAIEmbeddings for consistent embeddings across the
  pipeline (same model used in memory_check_node for query embedding).
- Persists to disk (``./chroma_data``) so cached reports survive restarts.
- Similarity threshold is configurable but defaults to 0.85 cosine similarity
  to avoid returning loosely related reports.
- Stores the full Report JSON in ChromaDB metadata so we can reconstruct
  the Pydantic model on retrieval without a separate database.
- A module-level ``get_memory_store()`` factory provides a lazy singleton
  so the store is initialised once and reused across nodes.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import chromadb
from chromadb.config import Settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from research_agent.models.schemas import MemoryHit, Report

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

_DEFAULT_COLLECTION = "research_reports"
_DEFAULT_PERSIST_DIR = "./chroma_data"
_DEFAULT_SIMILARITY_THRESHOLD = 0.85
_EMBEDDING_MODEL = "models/embedding-001"

# ── Singleton ───────────────────────────────────────────────────────────────

_instance: ChromaMemoryStore | None = None


def get_memory_store() -> ChromaMemoryStore:
    """Return a lazily-initialised singleton ``ChromaMemoryStore``.

    Called by graph nodes to avoid re-creating the ChromaDB client
    and embedding model on every invocation.
    """
    global _instance
    if _instance is None:
        _instance = ChromaMemoryStore()
    return _instance


# ── Store class ─────────────────────────────────────────────────────────────


class ChromaMemoryStore:
    """Semantic memory layer backed by ChromaDB.

    Responsibilities:
    1. Embed + store completed research reports.
    2. Query for similar past reports given a new user query.
    3. Return structured ``MemoryHit`` objects when similarity exceeds
       the configured threshold.

    All public methods are synchronous because ChromaDB's Python client
    is sync-only. Graph nodes call these inside ``asyncio.to_thread()``
    to avoid blocking the event loop.
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = _DEFAULT_COLLECTION,
        similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
    ) -> None:
        self._persist_dir = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIR", _DEFAULT_PERSIST_DIR
        )
        self._collection_name = collection_name
        self._similarity_threshold = similarity_threshold

        # ── ChromaDB client (persistent on-disk) ────────────────────────
        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # ── Embedding function ──────────────────────────────────────────
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GOOGLE_API_KEY must be set for GoogleGenerativeAIEmbeddings."
            )
        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=_EMBEDDING_MODEL,
            google_api_key=api_key,
        )

        logger.info(
            "ChromaMemoryStore initialised — collection=%s, persist=%s, "
            "docs=%d",
            self._collection_name,
            self._persist_dir,
            self._collection.count(),
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        n_results: int = 3,
    ) -> list[MemoryHit]:
        """Retrieve past reports whose query is semantically similar.

        Args:
            query_text: The user's new research query.
            n_results: Max number of results to return.

        Returns:
            List of ``MemoryHit`` objects with similarity above the
            configured threshold, sorted by descending similarity.
        """
        if self._collection.count() == 0:
            logger.debug("Memory is empty — skipping query.")
            return []

        query_embedding = self._embeddings.embed_query(query_text)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        hits: list[MemoryHit] = []

        # ChromaDB returns cosine *distance* when space="cosine".
        # similarity = 1 - distance.
        distances: list[float] = results["distances"][0] if results["distances"] else []
        documents: list[str] = results["documents"][0] if results["documents"] else []
        metadatas: list[dict[str, Any]] = (
            results["metadatas"][0] if results["metadatas"] else []
        )

        for dist, doc, meta in zip(distances, documents, metadatas):
            similarity = 1.0 - dist

            if similarity < self._similarity_threshold:
                continue

            hits.append(
                MemoryHit(
                    query=meta.get("original_query", ""),
                    report_summary=doc,
                    similarity_score=round(similarity, 4),
                    retrieved_at=datetime.now(timezone.utc),
                )
            )

        hits.sort(key=lambda h: h.similarity_score, reverse=True)
        logger.info(
            "Memory query returned %d hit(s) above threshold %.2f",
            len(hits),
            self._similarity_threshold,
        )
        return hits

    def store(self, query: str, report: Report) -> str:
        """Persist a completed report for future semantic retrieval.

        The report's JSON is stored as the ChromaDB *document* so it can
        be fully reconstructed on retrieval. The query text is embedded
        for similarity search.

        Args:
            query: The user's original research query.
            report: The completed ``Report`` Pydantic model.

        Returns:
            The ChromaDB document ID assigned to this entry.
        """
        report_json = report.model_dump_json()

        # Build a human-readable summary for the document field.
        section_headings = [s.heading for s in report.sections]
        summary = (
            f"Title: {report.title}\n"
            f"Quality: {report.quality_score:.2f}\n"
            f"Sections: {', '.join(section_headings)}\n"
            f"Citations: {len(report.citations)}"
        )

        query_embedding = self._embeddings.embed_query(query)

        doc_id = f"report_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        self._collection.add(
            ids=[doc_id],
            embeddings=[query_embedding],
            documents=[summary],
            metadatas=[
                {
                    "original_query": query,
                    "report_json": report_json,
                    "generated_at": report.generated_at.isoformat(),
                    "quality_score": report.quality_score,
                    "citation_count": len(report.citations),
                }
            ],
        )

        logger.info(
            "Stored report '%s' in memory (id=%s, quality=%.2f)",
            report.title,
            doc_id,
            report.quality_score,
        )
        return doc_id

    def get_report_from_hit(self, hit: MemoryHit) -> Report | None:
        """Reconstruct a full ``Report`` from a memory hit.

        Queries ChromaDB by the original query text to find the matching
        metadata entry containing the full report JSON.

        Args:
            hit: A ``MemoryHit`` returned by ``query()``.

        Returns:
            The reconstructed ``Report``, or ``None`` if not found.
        """
        if self._collection.count() == 0:
            return None

        query_embedding = self._embeddings.embed_query(hit.query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=1,
            include=["metadatas"],
        )

        metadatas = results.get("metadatas", [[]])
        if not metadatas or not metadatas[0]:
            return None

        report_json_str = metadatas[0][0].get("report_json")
        if not report_json_str:
            return None

        try:
            return Report.model_validate_json(report_json_str)
        except Exception:
            logger.exception("Failed to deserialize cached report.")
            return None

    @property
    def count(self) -> int:
        """Number of reports stored in memory."""
        return self._collection.count()

    def clear(self) -> None:
        """Delete all documents from the collection.

        Useful for testing and benchmark resets.
        """
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Memory cleared — collection '%s' reset.", self._collection_name)
