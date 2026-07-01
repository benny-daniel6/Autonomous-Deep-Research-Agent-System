"""
Tavily search API wrapper with timeout and error handling.

Wraps the synchronous Tavily client in asyncio.to_thread() so it
doesn't block the LangGraph event loop. Each search is capped at a
configurable timeout (default 10 s) to keep the pipeline responsive.
"""

from __future__ import annotations

import asyncio
import logging
import os

from tavily import TavilyClient

logger = logging.getLogger(__name__)


async def tavily_search(
    query: str,
    max_results: int = 5,
    timeout: float = 10.0,
) -> list[dict]:
    """Execute a Tavily web search with timeout protection.

    Args:
        query: Search query string.
        max_results: Maximum results to return.
        timeout: Seconds before the search is cancelled.

    Returns:
        List of result dicts with keys: ``title``, ``url``, ``content``, ``score``.
        Returns an empty list on timeout or any other failure.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        logger.error("TAVILY_API_KEY is not set.")
        return []

    client = TavilyClient(api_key=api_key)

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.search,
                query=query,
                max_results=max_results,
                search_depth="basic",
            ),
            timeout=timeout,
        )
        results = response.get("results", [])
        logger.info("Tavily returned %d results for: %s", len(results), query)
        return results

    except asyncio.TimeoutError:
        logger.warning(
            "Tavily search timed out after %.1fs for: %s", timeout, query
        )
        return []

    except Exception as e:
        logger.error("Tavily search failed for '%s': %s", query, e)
        return []
