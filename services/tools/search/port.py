"""WebSearchProvider Protocol port and SearchResult model.

This is the hexagonal port that adapters (SearXNG, stub) implement.
NO langgraph or langchain imports allowed.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A single web search result."""

    title: str = Field(description="Result title")
    url: str = Field(description="Result URL")
    snippet: str = Field(description="Excerpt/snippet text")


class WebSearchError(Exception):
    """Raised when a search provider encounters a non-retryable failure."""

    def __init__(self, message: str, *, provider: str, status_code: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class WebSearchEmpty(Exception):
    """Raised when a search provider returns zero results."""

    def __init__(self, query: str, *, provider: str):
        super().__init__(f"No results for query: {query!r}")
        self.query = query
        self.provider = provider


@runtime_checkable
class WebSearchProvider(Protocol):
    """Port: any web search backend must implement this contract."""

    def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Execute a web search and return results.

        Raises:
            WebSearchError: on HTTP/network/timeout failures.
            WebSearchEmpty: when the backend returns zero results.
        """
        ...
