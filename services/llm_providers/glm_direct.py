"""GLM (Z.ai) direct-call provider — a LiteLLM extension adapter.

LiteLLM does not map ``zai/glm-5.2``: it falls through to a bare OpenAI
passthrough with no model config, and the multi-turn ReAct tool loop sends an
``assistant{tool_calls}`` + ``tool`` message array that Z.ai's validator rejects
("messages parameter is illegal"), failing every multi-turn case.

This client bypasses LiteLLM and POSTs Z.ai's OpenAI-compatible
``/chat/completions`` endpoint directly with ``httpx`` — the exact message array
LiteLLM mangled goes on the wire verbatim. It is LangChain-free; the horizontal
boundary shim (services/llm_config.py:_DirectChatModel) maps the returned
``LLMCompletion`` onto an ``AIMessage`` for the call sites.

Hexagonal adapter (Horizontal layer): implements the ``LLMProvider`` port from
the Trust Foundation; imports only from ``trust/`` + stdlib + httpx.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from trust.exceptions import TrustProviderError
from trust.protocols import LLMCompletion

logger = logging.getLogger("services.llm_providers.glm_direct")

# Z.ai OpenAI-compatible chat-completions endpoint (the GLM-5 family).
GLM_BASE_URL = "https://api.z.ai/api/paas/v4"


class GLMDirectProvider:
    """Direct REST client for the GLM-5 family (Z.ai). Satisfies ``LLMProvider``."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = GLM_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        # An injected client (tests pass an httpx.MockTransport) keeps the unit
        # tests offline; in prod a default AsyncClient is created lazily.
        self._client = client
        self._timeout = timeout

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def acompletion(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMCompletion:
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._get_client().post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:  # network/transport failure
            raise TrustProviderError(
                f"GLM request failed: {exc}",
                provider="glm",
                operation="acompletion",
                original_error=exc,
            ) from exc

        if response.status_code >= 400:
            raise TrustProviderError(
                f"GLM returned HTTP {response.status_code}: {response.text[:500]}",
                provider="glm",
                operation="acompletion",
            )

        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise TrustProviderError(
                f"GLM returned non-JSON body: {response.text[:200]}",
                provider="glm",
                operation="acompletion",
                original_error=exc,
            ) from exc

        return _parse_completion(body)


def _parse_completion(body: dict) -> LLMCompletion:
    """Map a Z.ai chat-completion JSON body to the framework-agnostic contract."""
    choices = body.get("choices") or []
    if not choices:
        raise TrustProviderError(
            f"GLM response has no choices: {body!r}",
            provider="glm",
            operation="acompletion",
        )

    message = choices[0].get("message", {}) or {}
    content = _content_text(message.get("content"))
    tool_calls = _map_tool_calls(message.get("tool_calls") or [])

    usage_raw = body.get("usage") or {}
    usage = {
        "input_tokens": usage_raw.get("prompt_tokens", 0),
        "output_tokens": usage_raw.get("completion_tokens", 0),
    }
    return LLMCompletion(content=content, tool_calls=tool_calls, usage=usage, raw=body)


def _content_text(content: Any) -> str:
    """Collapse a GLM ``content`` to the answer string.

    GLM's default thinking mode can return ``content`` as a list of blocks
    (``{"type":"thinking",...}`` + ``{"type":"text","text":...}``). The thinking
    scratchpad must not leak — join only ``text`` blocks (same hazard the
    ``response_text`` helper handles for DeepSeek over LiteLLM). A plain string
    passes through; ``None`` → ``""``.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return str(content)


def _map_tool_calls(raw_calls: list[dict]) -> list[dict]:
    """OpenAI tool-call shape → LangChain ``{"name","args","id"}`` dict shape.

    The provider returns ``function.arguments`` as a JSON STRING; the loop binds
    LangChain tool calls whose ``args`` is a parsed dict. A non-JSON arguments
    string falls back to an empty dict (the call still dispatches by name).
    """
    mapped: list[dict] = []
    for call in raw_calls:
        fn = call.get("function", {}) or {}
        raw_args = fn.get("arguments", "")
        try:
            args = (
                json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            )
        except (json.JSONDecodeError, ValueError):
            args = {}
        mapped.append(
            {"name": fn.get("name", ""), "args": args, "id": call.get("id", "")}
        )
    return mapped
