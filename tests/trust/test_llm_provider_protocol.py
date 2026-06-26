"""L1 Deterministic: the direct-call LLM port (trust/protocols.py).

The ``LLMProvider`` Protocol + ``LLMCompletion`` value object are the
framework-agnostic contract a "LiteLLM extension" client satisfies when a model
is not served by LiteLLM (first case: GLM-5.2 over Z.ai's REST API). These live
in the Trust Foundation: pure types, no I/O, no langchain, no httpx.

Pure Red-Green-Refactor (Protocol A). Assertions are exact/structural; the only
"behavior" here is structural subtyping, which ``@runtime_checkable`` makes
testable without any network.
"""

from __future__ import annotations

from trust.protocols import LLMCompletion, LLMProvider


class TestLLMCompletion:
    """The LiteLLM-shaped, framework-agnostic completion value object."""

    def test_constructible_with_contract_fields(self):
        c = LLMCompletion(
            content="4",
            tool_calls=[{"name": "add", "args": {"a": 2, "b": 2}, "id": "call_1"}],
            usage={"input_tokens": 10, "output_tokens": 1},
            raw={"id": "chatcmpl-x"},
        )
        assert c.content == "4"
        assert c.tool_calls[0]["name"] == "add"
        assert c.usage["input_tokens"] == 10
        assert c.raw["id"] == "chatcmpl-x"

    def test_defaults_are_empty_not_none(self):
        """A no-tool, no-usage completion is the common case (plain answer) — the
        collections default to empty containers so call sites never special-case
        ``None`` (mirrors how the loop reads ``tool_calls``/``usage`` off a
        response with ``getattr(..., default)``)."""
        c = LLMCompletion(content="hi")
        assert c.tool_calls == []
        assert c.usage == {}
        assert c.raw == {}


class _ConformingProvider:
    async def acompletion(
        self, *, model, messages, tools=None, temperature=None, max_tokens=None
    ) -> LLMCompletion:  # pragma: no cover - structural conformance only
        return LLMCompletion(content="")


class _MissingMethod:
    pass


class TestLLMProviderProtocol:
    """Structural subtyping: any object exposing ``acompletion`` IS an
    ``LLMProvider`` (no ABC inheritance required), matching the existing
    ``IdentityProvider``/``PolicyProvider`` ports in this module."""

    def test_runtime_checkable_accepts_conforming_object(self):
        assert isinstance(_ConformingProvider(), LLMProvider)

    def test_runtime_checkable_rejects_nonconforming_object(self):
        # Failure path first: an object WITHOUT acompletion must NOT pass the
        # structural check — otherwise the factory could hand the loop a client
        # that can't be called.
        assert not isinstance(_MissingMethod(), LLMProvider)
