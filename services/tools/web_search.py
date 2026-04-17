"""Web search tool: stub returning canned response (real impl in Phase 2+)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")


class WebSearchOutput(BaseModel):
    results: list[dict[str, str]]
    query: str


def execute_web_search(args: dict[str, Any]) -> str:
    """Stub web search that returns a placeholder result."""
    try:
        validated = WebSearchInput(**args)
    except Exception as e:
        return f"Error: {e}"

    output = WebSearchOutput(
        query=validated.query,
        results=[
            {
                "title": f"Search result for: {validated.query}",
                "snippet": "This is a stub response. Real web search will be implemented in Phase 2.",
                "url": "https://example.com",
            }
        ],
    )
    return output.model_dump_json()
