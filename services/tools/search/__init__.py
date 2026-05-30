"""Provider-agnostic web search: port + adapters."""

from services.tools.search.port import SearchResult, WebSearchProvider

__all__ = ["SearchResult", "WebSearchProvider"]
