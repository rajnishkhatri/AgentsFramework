"""SearXNG adapter for WebSearchProvider.

Performs GET {base_url}/search?q=...&format=json&categories=general
and maps the JSON response to SearchResult models.

NO langgraph or langchain imports allowed.
"""

from __future__ import annotations

import logging

import httpx

from services.tools.search.port import (
    SearchResult,
    WebSearchEmpty,
    WebSearchError,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0
_DEFAULT_CATEGORIES = "general"


class SearxngProvider:
    """WebSearchProvider adapter backed by a SearXNG instance."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        categories: str = _DEFAULT_CATEGORIES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._categories = categories

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Execute a search via the SearXNG JSON API.

        Raises:
            WebSearchError: on HTTP/network/timeout failures.
            WebSearchEmpty: when the backend returns zero results.
        """
        params = {
            "q": query,
            "format": "json",
            "categories": self._categories,
        }
        try:
            response = httpx.get(
                f"{self._base_url}/search",
                params=params,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise WebSearchError(
                f"SearXNG timeout after {self._timeout}s for query: {query!r}",
                provider="searxng",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise WebSearchError(
                f"SearXNG HTTP {exc.response.status_code} for query: {query!r}",
                provider="searxng",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise WebSearchError(
                f"SearXNG network error for query: {query!r}: {exc}",
                provider="searxng",
            ) from exc

        data = response.json()
        raw_results = data.get("results", [])

        if not raw_results:
            raise WebSearchEmpty(query, provider="searxng")

        results: list[SearchResult] = []
        for item in raw_results[:max_results]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                )
            )

        return results


assert isinstance(SearxngProvider.__mro__[0], type)
