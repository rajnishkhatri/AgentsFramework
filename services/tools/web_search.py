"""Web search tool: provider-agnostic executor factory.

Exposes build_web_search_executor(provider) which returns a callable
compatible with ToolDefinition.executor. Returns ToolExecutionResult
with ok=False on provider failure/empty so the loop treats a dead
backend as terminal rather than retryable.

NO langgraph or langchain imports allowed.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

from services.guardrails import sanitize_retrieved_text
from services.tools.registry import ToolExecutionResult
from services.tools.search.port import (
    SearchResult,
    WebSearchEmpty,
    WebSearchError,
    WebSearchProvider,
)

logger = logging.getLogger(__name__)


class WebSearchInput(BaseModel):
    """Input schema for web_search tool."""

    query: str = Field(description="Search query")


class WebSearchOutput(BaseModel):
    """Output schema carrying real or stub results."""

    results: list[SearchResult]
    query: str
    provider: str = "unknown"
    sanitized: bool = False


def sanitize_search_results(
    results: list[SearchResult],
) -> tuple[list[SearchResult], list[str]]:
    """Strip indirect-injection payloads from retrieved snippets (S5-1).

    Runs the Retrieval-rail sanitizer over each result's ``title`` and
    ``snippet`` (the model-visible text). The ``url`` is left untouched —
    URLs are not model instructions and stripping them would break citation.
    Returns the (possibly rewritten) results plus the de-duplicated list of
    sanitization reasons across all results (empty ⇒ everything passed clean).
    """
    sanitized: list[SearchResult] = []
    reasons: list[str] = []
    for result in results:
        title = sanitize_retrieved_text(result.title)
        snippet = sanitize_retrieved_text(result.snippet)
        if not title.modified and not snippet.modified:
            sanitized.append(result)
            continue
        reasons.extend(title.flagged_reasons)
        reasons.extend(snippet.flagged_reasons)
        sanitized.append(
            result.model_copy(
                update={
                    "title": title.sanitized_text,
                    "snippet": snippet.sanitized_text,
                }
            )
        )
    return sanitized, list(dict.fromkeys(reasons))


def build_web_search_executor(
    provider: WebSearchProvider,
    *,
    sanitize: bool = True,
) -> Callable[[dict[str, Any]], ToolExecutionResult]:
    """Factory: returns a tool executor bound to the given search provider.

    When ``sanitize`` is ``True`` (the default, defense-in-depth), retrieved
    snippets are run through the Retrieval-rail sanitizer (S5-1) before they
    re-enter the model context.
    """

    def _execute(args: dict[str, Any]) -> ToolExecutionResult:
        try:
            validated = WebSearchInput(**args)
        except Exception as e:
            return ToolExecutionResult(
                output=f"Error: Invalid input: {e}",
                ok=False,
                error=f"validation_error: {e}",
                error_class="validation",
            )

        try:
            results = provider.search(validated.query, max_results=5)
        except WebSearchEmpty as exc:
            output = WebSearchOutput(
                query=validated.query,
                results=[],
                provider=exc.provider,
            )
            return ToolExecutionResult(
                output=output.model_dump_json(),
                ok=False,
                error=f"empty_results: {exc}",
            )
        except WebSearchError as exc:
            # Backend outage / provider fault is environmental, not the model's
            # malformed call nor a crash in our code.
            return ToolExecutionResult(
                output=f"Error: {exc}",
                ok=False,
                error=f"provider_error: {exc}",
                error_class="provider_error",
            )
        except Exception as exc:
            logger.exception("Unexpected error in web_search provider")
            return ToolExecutionResult(
                output=f"Error: unexpected failure: {exc}",
                ok=False,
                error=f"unexpected: {exc}",
                error_class="runtime",
            )

        sanitized_flag = False
        if sanitize:
            results, reasons = sanitize_search_results(results)
            if reasons:
                sanitized_flag = True
                logger.warning(
                    "web_search sanitized retrieved snippets: query=%r reasons=%s",
                    validated.query,
                    reasons,
                    extra={"flagged_reasons": reasons},
                )

        output = WebSearchOutput(
            query=validated.query,
            results=results,
            provider=getattr(
                provider, "_provider_name", type(provider).__name__.lower()
            ),
            sanitized=sanitized_flag,
        )
        return ToolExecutionResult(
            output=output.model_dump_json(),
            ok=True,
        )

    return _execute


def execute_web_search(args: dict[str, Any]) -> str:
    """Backward-compatible stub executor (no provider injection).

    Used by callers that haven't migrated to build_web_search_executor yet.
    """
    from services.tools.search.stub import StubProvider

    executor = build_web_search_executor(StubProvider())
    result = executor(args)
    return result.output
