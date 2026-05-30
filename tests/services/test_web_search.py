"""L2 Reproducible: Contract tests for services/tools/search/.

Contract-driven TDD per Protocol B (research/tdd_agentic_systems_prompt.md).
Failure paths first: provider errors, empty results, and timeouts tested
before success paths.

All tests use mocked httpx — no real network calls in CI.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from services.tools.registry import ToolExecutionResult
from services.tools.search.port import (
    SearchResult,
    WebSearchEmpty,
    WebSearchError,
    WebSearchProvider,
)
from services.tools.search.searxng import SearxngProvider
from services.tools.search.stub import StubProvider
from services.tools.web_search import WebSearchInput, WebSearchOutput, build_web_search_executor


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

SEARXNG_SUCCESS_RESPONSE = {
    "results": [
        {"title": "Austin Weather", "url": "https://weather.com/austin", "content": "Sunny, 85F"},
        {"title": "Austin TX Forecast", "url": "https://forecast.io/austin", "content": "Clear skies"},
    ]
}

SEARXNG_EMPTY_RESPONSE = {"results": []}


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://localhost:8888/search"),
    )


# ─────────────────────────────────────────────────────────────────────
# Protocol conformance: both adapters satisfy WebSearchProvider
# ─────────────────────────────────────────────────────────────────────


class TestProtocolConformance:
    def test_stub_satisfies_protocol(self):
        assert isinstance(StubProvider(), WebSearchProvider)

    def test_searxng_satisfies_protocol(self):
        assert isinstance(SearxngProvider(base_url="http://localhost:8888"), WebSearchProvider)


# ─────────────────────────────────────────────────────────────────────
# SearxngProvider — failure paths first
# ─────────────────────────────────────────────────────────────────────


class TestSearxngProviderFailures:
    """Failure paths tested before success paths (TAP-4 prevention)."""

    def test_http_error_raises_web_search_error(self):
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _mock_response({"error": "bad"}, status_code=500)
            mock_get.return_value.raise_for_status = lambda: (_ for _ in ()).throw(
                httpx.HTTPStatusError(
                    "Server Error",
                    request=httpx.Request("GET", "http://localhost:8888/search"),
                    response=mock_get.return_value,
                )
            )
            provider = SearxngProvider(base_url="http://localhost:8888")
            with pytest.raises(WebSearchError) as exc_info:
                provider.search("test query")
            assert exc_info.value.provider == "searxng"
            assert exc_info.value.status_code == 500

    def test_timeout_raises_web_search_error(self):
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            provider = SearxngProvider(base_url="http://localhost:8888", timeout=2.0)
            with pytest.raises(WebSearchError) as exc_info:
                provider.search("test query")
            assert exc_info.value.provider == "searxng"
            assert "timeout" in str(exc_info.value).lower()

    def test_network_error_raises_web_search_error(self):
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("connection refused")
            provider = SearxngProvider(base_url="http://localhost:8888")
            with pytest.raises(WebSearchError) as exc_info:
                provider.search("test query")
            assert exc_info.value.provider == "searxng"

    def test_empty_results_raises_web_search_empty(self):
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _mock_response(SEARXNG_EMPTY_RESPONSE)
            provider = SearxngProvider(base_url="http://localhost:8888")
            with pytest.raises(WebSearchEmpty) as exc_info:
                provider.search("obscure query xyz")
            assert exc_info.value.provider == "searxng"
            assert exc_info.value.query == "obscure query xyz"


# ─────────────────────────────────────────────────────────────────────
# SearxngProvider — success paths
# ─────────────────────────────────────────────────────────────────────


class TestSearxngProviderSuccess:
    def test_success_returns_search_results(self):
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _mock_response(SEARXNG_SUCCESS_RESPONSE)
            provider = SearxngProvider(base_url="http://localhost:8888")
            results = provider.search("austin weather")
            assert len(results) == 2
            assert all(isinstance(r, SearchResult) for r in results)
            assert results[0].title == "Austin Weather"
            assert results[0].url == "https://weather.com/austin"
            assert results[0].snippet == "Sunny, 85F"

    def test_max_results_limits_output(self):
        many_results = {
            "results": [
                {"title": f"Result {i}", "url": f"https://example.com/{i}", "content": f"Snippet {i}"}
                for i in range(20)
            ]
        }
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _mock_response(many_results)
            provider = SearxngProvider(base_url="http://localhost:8888")
            results = provider.search("many results", max_results=3)
            assert len(results) == 3

    def test_passes_correct_query_params(self):
        with patch("httpx.get") as mock_get:
            mock_get.return_value = _mock_response(SEARXNG_SUCCESS_RESPONSE)
            provider = SearxngProvider(base_url="http://searxng:8888", categories="news")
            provider.search("test")
            call_kwargs = mock_get.call_args
            assert call_kwargs[0][0] == "http://searxng:8888/search"
            assert call_kwargs[1]["params"]["q"] == "test"
            assert call_kwargs[1]["params"]["format"] == "json"
            assert call_kwargs[1]["params"]["categories"] == "news"


# ─────────────────────────────────────────────────────────────────────
# StubProvider
# ─────────────────────────────────────────────────────────────────────


class TestStubProvider:
    def test_returns_deterministic_canned_result(self):
        provider = StubProvider()
        results = provider.search("anything")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert "anything" in results[0].title

    def test_never_raises(self):
        provider = StubProvider()
        results = provider.search("")
        assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────────────
# build_web_search_executor integration (executor factory)
# ─────────────────────────────────────────────────────────────────────


class TestBuildWebSearchExecutor:
    """Tests the executor factory with injected providers."""

    def test_success_returns_ok_true(self):
        executor = build_web_search_executor(StubProvider())
        result = executor({"query": "hello"})
        assert isinstance(result, ToolExecutionResult)
        assert result.ok is True
        output = json.loads(result.output)
        assert output["query"] == "hello"
        assert len(output["results"]) >= 1

    def test_invalid_input_returns_ok_false(self):
        executor = build_web_search_executor(StubProvider())
        result = executor({})
        assert result.ok is False
        assert "validation_error" in (result.error or "")

    def test_provider_error_returns_ok_false(self):
        class FailingProvider:
            def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
                raise WebSearchError("backend down", provider="test")

        executor = build_web_search_executor(FailingProvider())
        result = executor({"query": "test"})
        assert result.ok is False
        assert "provider_error" in (result.error or "")

    def test_empty_results_returns_ok_false(self):
        class EmptyProvider:
            def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
                raise WebSearchEmpty(query, provider="test")

        executor = build_web_search_executor(EmptyProvider())
        result = executor({"query": "nothing"})
        assert result.ok is False
        assert "empty_results" in (result.error or "")
        output = json.loads(result.output)
        assert output["results"] == []


# ─────────────────────────────────────────────────────────────────────
# Provider selection (env-based)
# ─────────────────────────────────────────────────────────────────────


class TestProviderSelection:
    def test_default_is_stub(self, monkeypatch):
        monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
        monkeypatch.delenv("SEARXNG_URL", raising=False)
        from services.tools.web_search import execute_web_search

        result = execute_web_search({"query": "fallback test"})
        assert "stub" in result.lower()

    def test_stub_explicit(self, monkeypatch):
        monkeypatch.setenv("WEB_SEARCH_PROVIDER", "stub")
        from services.tools.web_search import execute_web_search

        result = execute_web_search({"query": "explicit stub"})
        assert len(result) > 0


# ─────────────────────────────────────────────────────────────────────
# Backward compatibility: execute_web_search still works
# ─────────────────────────────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_execute_web_search_returns_string(self):
        from services.tools.web_search import execute_web_search

        result = execute_web_search({"query": "compat test"})
        assert isinstance(result, str)
        assert len(result) > 0
