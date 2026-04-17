"""L2 Contract: Sandbox-as-tool tests (Story 5.3).

Tests that SandboxExecutor satisfies the ToolRegistry.execute() interface.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from services.tools.registry import ToolDefinition, ToolRegistry
from services.tools.sandbox import LocalSandboxExecutor, RemoteSandboxExecutor


class _EchoInput(BaseModel):
    value: str


def _echo(args: dict) -> str:
    return f"echo:{args.get('value', '')}"


def _build_registry() -> ToolRegistry:
    return ToolRegistry({
        "echo": ToolDefinition(executor=_echo, schema=_EchoInput, cacheable=True),
    })


class TestLocalSandboxExecutor:
    def test_execute_matches_registry_contract(self):
        registry = _build_registry()
        sandbox = LocalSandboxExecutor(registry)

        result = sandbox.execute("echo", {"value": "hello"})
        expected = registry.execute("echo", {"value": "hello"})
        assert result == expected

    def test_cleanup_prevents_further_execution(self):
        registry = _build_registry()
        sandbox = LocalSandboxExecutor(registry)

        sandbox.cleanup()
        with pytest.raises(RuntimeError, match="cleaned up"):
            sandbox.execute("echo", {"value": "hello"})

    def test_cleanup_called_on_tool_failure(self):
        def _failing(args: dict) -> str:
            raise RuntimeError("Tool broke")

        registry = ToolRegistry({
            "fail": ToolDefinition(executor=_failing, schema=_EchoInput, cacheable=False),
        })
        sandbox = LocalSandboxExecutor(registry)

        with pytest.raises(RuntimeError, match="Tool broke"):
            sandbox.execute("fail", {"value": "x"})

        with pytest.raises(RuntimeError, match="cleaned up"):
            sandbox.execute("fail", {"value": "x"})


class TestRemoteSandboxExecutor:
    def test_constructor_accepts_config(self):
        sandbox = RemoteSandboxExecutor(
            api_url="http://localhost:8080",
            api_key="test-key",
            timeout_seconds=30,
        )
        assert sandbox._api_url == "http://localhost:8080"
        assert sandbox._session_id is None

    def test_cleanup_without_session_is_noop(self):
        sandbox = RemoteSandboxExecutor(
            api_url="http://localhost:8080",
            api_key="test-key",
        )
        sandbox.cleanup()
        assert sandbox._session_id is None
