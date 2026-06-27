"""Stub adapter: returns canned results for CI/offline use.

NO langgraph or langchain imports allowed.
"""

from __future__ import annotations

from services.tools.search.port import SearchResult


class StubProvider:
    """WebSearchProvider adapter that returns deterministic canned results.

    Used as the default when WEB_SEARCH_PROVIDER is unset or set to 'stub'.
    Keeps CI network-free.
    """

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title=f"Search result for: {query}",
                url="https://example.com",
                snippet="This is a stub response. Real web search is available via SearXNG.",
            )
        ]


assert isinstance(StubProvider.__mro__[0], type)
