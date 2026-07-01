"""
Wikipedia fallback search using the ``wikipedia-api`` package.

Used when Tavily returns fewer than 2 results for a search query.
Wraps the synchronous Wikipedia client in ``asyncio.to_thread()``
to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging

import wikipediaapi

logger = logging.getLogger(__name__)


async def wikipedia_search(
    query: str,
    max_chars: int = 4000,
) -> list[dict]:
    """Look up a Wikipedia page matching *query* and return its summary.

    The ``wikipedia-api`` package only supports page lookup (not full-text
    search), so we try the query string directly as a page title.  If
    the exact title doesn't match, we also try a version with spaces
    replaced by underscores.

    Args:
        query: Topic or page title to look up.
        max_chars: Maximum characters of page summary to return.

    Returns:
        A list containing at most one result dict with keys:
        ``title``, ``url``, ``content``.  Empty list if no page found.
    """

    def _lookup() -> list[dict]:
        wiki = wikipediaapi.Wikipedia(
            user_agent="MultiAgentResearcher/1.0 (research project)",
            language="en",
        )

        # Attempt 1: exact query as page title
        page = wiki.page(query)
        if page.exists():
            return [
                {
                    "title": page.title,
                    "url": page.fullurl,
                    "content": (page.summary or "")[:max_chars],
                }
            ]

        # Attempt 2: underscored variant
        alt_query = query.replace(" ", "_")
        page = wiki.page(alt_query)
        if page.exists():
            return [
                {
                    "title": page.title,
                    "url": page.fullurl,
                    "content": (page.summary or "")[:max_chars],
                }
            ]

        return []

    try:
        results = await asyncio.to_thread(_lookup)
        logger.info(
            "Wikipedia returned %d result(s) for: %s", len(results), query
        )
        return results

    except Exception as e:
        logger.error("Wikipedia search failed for '%s': %s", query, e)
        return []
