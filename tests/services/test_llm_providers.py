"""L2 Reproducible: the direct-call LLM providers (services/llm_providers/).

Contract-driven TDD for the "LiteLLM extension" — a client that calls a
provider's REST API directly for models LiteLLM cannot serve (first case:
GLM-5.2 over Z.ai's OpenAI-compatible endpoint).

ALL network I/O is mocked with ``httpx.MockTransport`` — never ``api.z.ai`` (a
live round-trip is a separate ``@pytest.mark.live_llm`` smoke). Failure paths
first (Anti-Pattern 6): a non-2xx / malformed response must raise a typed
``TrustProviderError`` BEFORE the happy-path mapping is asserted.
"""

from __future__ import annotations

import httpx
import pytest

from services.llm_providers import get_direct_provider
from services.llm_providers.glm_direct import GLMDirectProvider
from trust.exceptions import TrustProviderError
from trust.protocols import LLMCompletion, LLMProvider

# A realistic multi-turn ReAct array: system, human, the assistant turn that
# carries ``tool_calls`` with EMPTY content, then the tool result. This exact
# shape is what LiteLLM's unmapped-glm-5.2 passthrough mangles into the Z.ai
# "messages parameter is illegal" rejection — the direct client must send it
# verbatim.
MULTI_TURN_MESSAGES = [
    {"role": "system", "content": "You are a calculator."},
    {"role": "user", "content": "2+2?"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "add", "arguments": '{"a": 2, "b": 2}'},
            }
        ],
    },
    {"role": "tool", "tool_call_id": "call_1", "content": "4"},
]


def _provider_with_transport(handler) -> GLMDirectProvider:
    """A GLMDirectProvider whose AsyncClient uses a MockTransport (no network)."""
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GLMDirectProvider(api_key="test-key", client=client)


# ── Failure paths first ──────────────────────────────────────────────────────


class TestGLMDirectFailurePaths:
    async def test_non_2xx_raises_trust_provider_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"message": "messages illegal"}})

        provider = _provider_with_transport(handler)
        with pytest.raises(TrustProviderError) as exc:
            await provider.acompletion(model="glm-5.2", messages=MULTI_TURN_MESSAGES)
        # Typed, attributable error — provider + operation populated so the
        # runtime can log which client/op failed (mirrors cloud_providers).
        assert exc.value.provider == "glm"
        assert exc.value.operation == "acompletion"

    async def test_malformed_json_body_raises_trust_provider_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json at all")

        provider = _provider_with_transport(handler)
        with pytest.raises(TrustProviderError):
            await provider.acompletion(model="glm-5.2", messages=MULTI_TURN_MESSAGES)

    async def test_missing_choices_raises_trust_provider_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "x", "choices": []})

        provider = _provider_with_transport(handler)
        with pytest.raises(TrustProviderError):
            await provider.acompletion(model="glm-5.2", messages=MULTI_TURN_MESSAGES)


# ── Happy path: request fidelity + response mapping ──────────────────────────


class TestGLMDirectHappyPath:
    async def test_multi_turn_messages_sent_verbatim(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            captured["body"] = json.loads(request.content)
            captured["auth"] = request.headers.get("authorization")
            captured["url"] = str(request.url)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "4"}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 1},
                },
            )

        provider = _provider_with_transport(handler)
        await provider.acompletion(model="glm-5.2", messages=MULTI_TURN_MESSAGES)

        # The exact multi-turn array (assistant tool_calls + tool result) reaches
        # the provider — the case LiteLLM mangled. Verbatim, in order.
        assert captured["body"]["messages"] == MULTI_TURN_MESSAGES
        assert captured["body"]["model"] == "glm-5.2"
        assert captured["auth"] == "Bearer test-key"
        assert "chat/completions" in captured["url"]

    async def test_response_maps_to_llm_completion(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-1",
                    "choices": [{"message": {"content": "The answer is 4"}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                },
            )

        provider = _provider_with_transport(handler)
        result = await provider.acompletion(
            model="glm-5.2", messages=MULTI_TURN_MESSAGES
        )
        assert isinstance(result, LLMCompletion)
        assert result.content == "The answer is 4"
        # Provider usage keys are normalized to the loop's token-channel names.
        assert result.usage == {"input_tokens": 12, "output_tokens": 4}
        assert result.raw["id"] == "chatcmpl-1"

    async def test_tool_calls_mapped_to_langchain_dict_shape(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_42",
                                        "type": "function",
                                        "function": {
                                            "name": "add",
                                            "arguments": '{"a": 2, "b": 2}',
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 0},
                },
            )

        provider = _provider_with_transport(handler)
        result = await provider.acompletion(
            model="glm-5.2", messages=MULTI_TURN_MESSAGES
        )
        # OpenAI tool-call shape (function.arguments JSON string) → LangChain
        # dict shape (parsed args), the shape the loop binds into AIMessage.
        assert result.tool_calls == [
            {"name": "add", "args": {"a": 2, "b": 2}, "id": "call_42"}
        ]

    async def test_thinking_block_content_collapsed_to_answer_text(self):
        """GLM's default thinking mode can return ``content`` as a list of blocks
        (thinking + text). The client must return the ANSWER text only — the
        thinking scratchpad must not leak (same hazard as DeepSeek over LiteLLM)."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "thinking", "thinking": "2+2 is 4"},
                                    {"type": "text", "text": "4"},
                                ]
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 1},
                },
            )

        provider = _provider_with_transport(handler)
        result = await provider.acompletion(
            model="glm-5.2", messages=MULTI_TURN_MESSAGES
        )
        assert result.content == "4"
        assert "thinking" not in result.content

    async def test_live_observed_shape_reasoning_content_field_excluded(self):
        """The shape GLM-5.2 ACTUALLY returns (observed live 2026-06-26):
        ``content`` is the clean answer STRING and the chain-of-thought rides a
        SEPARATE ``reasoning_content`` field. Only ``content`` must surface — the
        reasoning trace must never leak into the answer (and is preserved in
        ``raw`` for debugging)."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "17 + 25 = **42**",
                                "reasoning_content": "Let me add 17 and 25...",
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 25, "completion_tokens": 96},
                },
            )

        provider = _provider_with_transport(handler)
        result = await provider.acompletion(
            model="glm-5.2", messages=MULTI_TURN_MESSAGES
        )
        assert result.content == "17 + 25 = **42**"
        assert "Let me add" not in result.content  # reasoning must not leak
        # reasoning_content is still in raw for audit/debugging.
        assert result.raw["choices"][0]["message"]["reasoning_content"]


# ── Factory ──────────────────────────────────────────────────────────────────


class _StubProvider:
    """A stub LLMProvider that records its call and returns a canned completion.

    Stubs ONLY the port (not over-mocked): the shim's job is the LangChain<->dict
    boundary mapping, which we assert against this recorded call + return."""

    def __init__(self, completion: LLMCompletion) -> None:
        self._completion = completion
        self.calls: list[dict] = []

    async def acompletion(
        self, *, model, messages, tools=None, temperature=None, max_tokens=None
    ) -> LLMCompletion:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "max_tokens": max_tokens,
            }
        )
        return self._completion


class TestDirectChatModelShim:
    """The boundary shim (services/llm_config.py:_DirectChatModel) — the ONLY
    place LangChain meets the direct client. ``bind_tools().ainvoke([...])`` must
    return an ``AIMessage`` shaped exactly like what ``call_llm_node`` reads."""

    def _profile(self):
        from services.base_config import ModelProfile

        return ModelProfile(
            name="glm-5.2",
            litellm_id="glm-5.2",
            tier="reasoning",
            context_window=200000,
            cost_per_1k_input=0.0012,
            cost_per_1k_output=0.0041,
            provider="direct",
            max_output_tokens=8192,
        )

    async def test_ainvoke_returns_aimessage_with_loop_read_attrs(self):
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        from services.llm_config import _DirectChatModel

        stub = _StubProvider(
            LLMCompletion(
                content="4",
                tool_calls=[],
                usage={"input_tokens": 12, "output_tokens": 1},
                raw={"id": "x"},
            )
        )
        model = _DirectChatModel(provider=stub, profile=self._profile())
        result = await model.ainvoke(
            [SystemMessage(content="calc"), HumanMessage(content="2+2?")]
        )
        # The exact attribute surface call_llm_node reads (react_loop.py:1852/1892).
        assert isinstance(result, AIMessage)
        assert result.content == "4"
        assert result.tool_calls == []
        assert result.usage_metadata["input_tokens"] == 12
        assert result.usage_metadata["output_tokens"] == 1

    async def test_lc_messages_converted_to_provider_dicts(self):
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        from services.llm_config import _DirectChatModel

        stub = _StubProvider(LLMCompletion(content="ok"))
        model = _DirectChatModel(provider=stub, profile=self._profile())

        # A multi-turn array incl. an assistant turn carrying tool_calls and a
        # ToolMessage — the case LiteLLM mangled. The shim must serialize it to
        # the OpenAI dict shape the GLM client sends verbatim.
        ai_with_tools = AIMessage(
            content="",
            tool_calls=[{"name": "add", "args": {"a": 2, "b": 2}, "id": "call_1"}],
        )
        await model.ainvoke(
            [
                HumanMessage(content="2+2?"),
                ai_with_tools,
                ToolMessage(content="4", tool_call_id="call_1"),
            ]
        )
        sent = stub.calls[0]["messages"]
        assert sent[0] == {"role": "user", "content": "2+2?"}
        # assistant turn carries OpenAI-shaped tool_calls
        assert sent[1]["role"] == "assistant"
        assert sent[1]["tool_calls"][0]["function"]["name"] == "add"
        assert sent[1]["tool_calls"][0]["id"] == "call_1"
        # tool result carries its tool_call_id
        assert sent[2] == {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "4",
        }

    async def test_bind_tools_normalizes_registry_schema_to_openai_envelope(self):
        """The tool registry (services/tools/registry.py:get_schemas) emits a FLAT
        shape ``{name, description, parameters}`` — the same one ChatLiteLLM
        normalizes before sending. Z.ai REQUIRES the OpenAI envelope
        ``{"type":"function","function":{...}}`` (else HTTP 400 "tools[0].type:
        type cannot be empty"), so the shim must wrap each flat schema. Regression
        for the live toolfail_glm52_l1 run."""
        from langchain_core.messages import HumanMessage

        from services.llm_config import _DirectChatModel

        stub = _StubProvider(LLMCompletion(content="ok"))
        model = _DirectChatModel(provider=stub, profile=self._profile())
        # Exactly what registry.get_schemas() returns.
        registry_schema = [
            {
                "name": "file_io",
                "description": "Read or write a file.",
                "parameters": {"type": "object", "properties": {}},
            }
        ]
        bound = model.bind_tools(registry_schema)
        await bound.ainvoke([HumanMessage(content="2+2?")])
        sent_tools = stub.calls[0]["tools"]
        assert sent_tools == [
            {
                "type": "function",
                "function": {
                    "name": "file_io",
                    "description": "Read or write a file.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        assert stub.calls[0]["max_tokens"] == 8192

    async def test_assistant_first_history_gets_leading_user_turn(self):
        """Z.ai rejects a conversation whose first non-system message is
        ``assistant`` ("messages parameter is illegal") — it requires a ``user``
        turn first. On the react-loop synthesis call the history is
        ``system → assistant(tool_calls) → tool…`` with NO user message, so the
        shim must inject a minimal leading user turn. Regression for the live
        toolfail_glm52_l1 step-20 failure (root-caused 2026-06-26)."""
        from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

        from services.llm_config import _DirectChatModel

        stub = _StubProvider(LLMCompletion(content="42"))
        model = _DirectChatModel(provider=stub, profile=self._profile())
        await model.ainvoke(
            [
                SystemMessage(content="You are a ReAct agent."),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "file_io", "args": {"path": "a"}, "id": "c1"}],
                ),
                ToolMessage(content="7", tool_call_id="c1"),
            ]
        )
        roles = [m["role"] for m in stub.calls[0]["messages"]]
        # system stays first; a user turn is inserted before the assistant turn.
        assert roles[0] == "system"
        assert roles[1] == "user"
        assert roles[2] == "assistant"

    async def test_user_first_history_unchanged(self):
        """A well-formed history (user already precedes assistant) is NOT
        modified — no spurious injected turn."""
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

        from services.llm_config import _DirectChatModel

        stub = _StubProvider(LLMCompletion(content="ok"))
        model = _DirectChatModel(provider=stub, profile=self._profile())
        await model.ainvoke(
            [
                HumanMessage(content="read a"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "file_io", "args": {"path": "a"}, "id": "c1"}],
                ),
                ToolMessage(content="7", tool_call_id="c1"),
            ]
        )
        roles = [m["role"] for m in stub.calls[0]["messages"]]
        assert roles == ["user", "assistant", "tool"]

    async def test_bind_tools_passes_through_already_enveloped_schema(self):
        """An already-OpenAI-shaped schema (``type``+``function`` present) is sent
        unchanged — idempotent normalization, no double-wrapping."""
        from langchain_core.messages import HumanMessage

        from services.llm_config import _DirectChatModel

        stub = _StubProvider(LLMCompletion(content="ok"))
        model = _DirectChatModel(provider=stub, profile=self._profile())
        enveloped = [{"type": "function", "function": {"name": "add"}}]
        await model.bind_tools(enveloped).ainvoke([HumanMessage(content="2+2?")])
        assert stub.calls[0]["tools"] == enveloped


class TestGetDirectProvider:
    def test_returns_glm_provider_for_glm_profile(self, monkeypatch):
        monkeypatch.setenv("GLM_API_KEY", "k")
        from services.base_config import ModelProfile

        profile = ModelProfile(
            name="glm-5.2",
            litellm_id="glm-5.2",
            tier="reasoning",
            context_window=200000,
            cost_per_1k_input=0.0012,
            cost_per_1k_output=0.0041,
            provider="direct",
        )
        provider = get_direct_provider(profile)
        assert isinstance(provider, LLMProvider)
        assert isinstance(provider, GLMDirectProvider)

    def test_unknown_direct_model_raises(self, monkeypatch):
        monkeypatch.setenv("GLM_API_KEY", "k")
        from services.base_config import ModelProfile

        profile = ModelProfile(
            name="mystery-1",
            litellm_id="mystery-1",
            tier="fast",
            context_window=1000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            provider="direct",
        )
        with pytest.raises(TrustProviderError):
            get_direct_provider(profile)
