"""Sandbox-as-tool architecture for safe tool execution.

In development, tools run locally via LocalSandboxExecutor.
In production, tools are delegated to ephemeral sandboxes via API.
The agent holds API keys on the host; the sandbox is destroyed after each task.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from services.tools.registry import ToolRegistry

logger = logging.getLogger("services.tools.sandbox")


class SandboxExecutor(ABC):
    """Abstract interface matching ToolRegistry.execute() contract."""

    @abstractmethod
    def execute(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        """Execute a tool in the sandbox and return its output."""
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Release sandbox resources."""
        ...


class LocalSandboxExecutor(SandboxExecutor):
    """Local executor: delegates directly to ToolRegistry (dev mode)."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._registry = tool_registry
        self._active = True

    def execute(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        if not self._active:
            raise RuntimeError("Sandbox has been cleaned up")
        try:
            return self._registry.execute(tool_name, tool_args)
        except Exception:
            self.cleanup()
            raise

    def cleanup(self) -> None:
        self._active = False
        logger.info("Local sandbox cleaned up")


class RemoteSandboxExecutor(SandboxExecutor):
    """Remote executor: delegates to an ephemeral sandbox API (production mode).

    Communicates with sandbox services (E2B, Modal, gVisor) via HTTP API.
    The sandbox is created on first execute() and destroyed on cleanup().
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout_seconds: int = 60,
    ) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._session_id: str | None = None

    def execute(self, tool_name: str, tool_args: dict[str, Any]) -> str:
        import json

        try:
            import urllib.request

            payload = json.dumps({
                "tool_name": tool_name,
                "tool_args": tool_args,
                "session_id": self._session_id,
            }).encode()

            req = urllib.request.Request(
                f"{self._api_url}/execute",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result = json.loads(resp.read().decode())
                self._session_id = result.get("session_id", self._session_id)
                return result.get("output", "")
        except Exception as exc:
            logger.error("Remote sandbox execution failed: %s", exc)
            self.cleanup()
            raise

    def cleanup(self) -> None:
        if self._session_id is None:
            return
        try:
            import json
            import urllib.request

            payload = json.dumps({"session_id": self._session_id}).encode()
            req = urllib.request.Request(
                f"{self._api_url}/cleanup",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            logger.warning("Sandbox cleanup failed: %s", exc)
        finally:
            self._session_id = None
            logger.info("Remote sandbox session ended")
