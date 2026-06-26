"""ModelProfile registry and ChatLiteLLM factory (H2 pattern).

Provides LLM access via LiteLLM's LangChain-compatible wrapper.
This is the only file in services/ allowed to import from langchain.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from services.base_config import AgentConfig, ModelProfile

logger = logging.getLogger("services.llm_config")


# litellm's ``zai`` provider (serving the GLM-5 family) reads its key from ``ZAI_API_KEY``,
# but this repo's key is provided as ``GLM_API_KEY``. Bridge env→env once at import
# (only when ZAI_API_KEY is unset) so a GLM pin resolves without a per-call api_key.
# No secret is hardcoded; this just aliases one env var to another.
if not os.environ.get("ZAI_API_KEY") and os.environ.get("GLM_API_KEY"):
    os.environ["ZAI_API_KEY"] = os.environ["GLM_API_KEY"]


# ── Central model registry (H2: the single source of truth for model names) ──
#
# Data-driven profile table keyed by ``MODEL_PROFILE_SET``. Adding or swapping a
# model later (e.g. claude-sonnet-4-6 -> 4-7, or a new gpt-5.5) is editing one
# row here — no router/call-site change (the router selects by *tier*, never by
# a hardcoded name; see components/router.py). The composition root, the CLIs,
# and the synthetic-batch script all consume this via ``build_model_registry``.
#
# ORDER IS A SAFETY CONTRACT: the router resolves a tier by first-match
# (``_pick_profile_by_tier``), so within each set the first ``fast`` / first
# ``capable`` / first ``reasoning`` profile is the one Auto routing picks. The
# ``"anthropic"`` set is ordered so first-match resolves fast->Haiku,
# capable->Sonnet, reasoning->Opus; the OpenAI models that follow are pin-only
# (a user can pin them by name, but Auto never reaches them). Regression tests
# in tests/services/test_llm_config.py pin this invariant.

_OPENAI_PROFILES: list[ModelProfile] = [
    ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
    ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    ),
]

# The 3-tier all-Anthropic Auto stack (decided 2026-06-24): fast=Haiku 4.5,
# capable=Sonnet 4.6, reasoning=Opus 4.8. The gpt-* models stay registered but
# pin-only (listed after the Anthropic tiers so first-match never reaches them).
_ANTHROPIC_PROFILES: list[ModelProfile] = [
    ModelProfile(
        name="claude-haiku-4-5",
        litellm_id="anthropic/claude-haiku-4-5",
        tier="fast",
        context_window=200000,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.005,
    ),
    ModelProfile(
        name="claude-sonnet-4-6",
        litellm_id="anthropic/claude-sonnet-4-6",
        tier="capable",
        context_window=1000000,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
    ),
    ModelProfile(
        name="claude-opus-4-8",
        litellm_id="anthropic/claude-opus-4-8",
        tier="reasoning",
        context_window=1000000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.025,
        # Opus 4.8 deprecated the ``temperature`` request param: sending one 400s
        # (invalid_request_error) before any token is generated, which the
        # runtime renders as the empty-output placeholder ($0 / 0 tokens). Omit
        # it for this model. Verified live 2026-06-25.
        supports_temperature=False,
        # Reasoning tier: give thinking tokens headroom so the answer is never
        # starved (see deepseek-v4-flash empty-output at 4096).
        max_output_tokens=8192,
    ),
    # The gpt-5 reasoning family rejects ``temperature=0`` (litellm raises
    # UnsupportedParamsError: "only temperature=1 is supported") — same empty-
    # output failure class as Opus 4.8. Omit the param for these too. Verified
    # live 2026-06-25. (gpt-5's reasoning can also consume the whole completion
    # budget on a tiny max_tokens, but at the get_llm default of 4096 it leaves
    # ample room for the answer — not a concern on the production path.)
    ModelProfile(
        name="gpt-5-mini",
        litellm_id="openai/gpt-5-mini",
        tier="fast",
        context_window=400000,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.002,
        supports_temperature=False,
        # Reasoning family: thinking tokens count against the budget; raise it
        # so a verbose reasoning trace can't starve the answer.
        max_output_tokens=8192,
    ),
    ModelProfile(
        name="gpt-5",
        litellm_id="openai/gpt-5",
        tier="capable",
        context_window=400000,
        cost_per_1k_input=0.00125,
        cost_per_1k_output=0.010,
        supports_temperature=False,
        max_output_tokens=8192,
    ),
    *_OPENAI_PROFILES,
]

# The DeepSeek V4 Auto stack (decided 2026-06-24): fast=Flash, capable=Flash
# (same litellm_id, DISTINCT name so _profiles keys don't collide and pin lookup
# stays unique), reasoning=Pro. Flash fills both fast and capable because the
# benchmark gap to Pro is tiny (SWE-Bench 79.0 vs 80.6) and DeepSeek's automatic
# caching makes the repeated ReAct prefix ~free at either tier — so paying Pro's
# 3.1x cache-MISS input premium on every planning/eval turn buys almost nothing.
# Pro is reachable by Auto ONLY via Branch 3 failure-escalation (reasoning tier),
# honoring "Pro = reasoning/complex". The gpt-* models stay registered but
# pin-only (listed after the DeepSeek tiers so first-match never reaches them).
# Legacy deepseek-chat/deepseek-reasoner aliases deprecate 2026-07-24 — the
# deepseek-v4-* IDs below are the current ones.
_DEEPSEEK_PROFILES: list[ModelProfile] = [
    ModelProfile(
        name="deepseek-v4-flash",
        litellm_id="deepseek/deepseek-v4-flash",
        tier="fast",
        context_window=1000000,
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        # DeepSeek V4 emits ``thinking`` tokens that count against the budget; at
        # 4096 a verbose trace can consume the whole budget and return an empty
        # answer (observed live 2026-06-25). 8192 leaves room for the answer.
        max_output_tokens=8192,
    ),
    ModelProfile(
        # Same litellm_id as deepseek-v4-flash — a DISTINCT name so LLMService
        # ._profiles (keyed by name) and the pin lookup don't collide. Flash
        # fills the capable tier too; see the rationale block above.
        name="deepseek-v4-flash-capable",
        litellm_id="deepseek/deepseek-v4-flash",
        tier="capable",
        context_window=1000000,
        cost_per_1k_input=0.00014,
        cost_per_1k_output=0.00028,
        max_output_tokens=8192,
    ),
    ModelProfile(
        name="deepseek-v4-pro",
        litellm_id="deepseek/deepseek-v4-pro",
        tier="reasoning",
        context_window=1000000,
        cost_per_1k_input=0.000435,
        cost_per_1k_output=0.00087,
        max_output_tokens=8192,
    ),
    *_OPENAI_PROFILES,
]

# GLM-5 family (Zhipu/Z.ai, MIT) — the research's #1 tool-caller tier (τ²-bench
# Telecom ~99%). Served direct via litellm's native ``zai`` provider, which reads
# the key from ``ZAI_API_KEY`` (the GLM_API_KEY→ZAI_API_KEY env alias below bridges
# the user's key name). Pin-only (never an Auto stack); reasoning tier. The default
# thinking mode bills + consumes the completion budget like DeepSeek/gpt-5, so it
# carries an 8192 budget to avoid empty-output-at-4096; the thinking-block content
# shape is handled by ``response_text`` (same path as DeepSeek).
#
# Two GLM rows, both pin-only / reasoning tier:
#
#   glm-5.2 (provider="direct") — the research's GLM-5 reliability pick. litellm
#     does NOT map ``zai/glm-5.2`` (latest mapped is glm-5.1): it falls through to
#     a bare OpenAI passthrough with no model config, and the multi-turn ReAct
#     tool loop sends a message array (assistant with empty content + tool_calls,
#     then a tool message) that Z.ai's validator rejects with "messages parameter
#     is illegal" — failing every multi-turn case. So glm-5.2 is routed through
#     the direct-call extension (services/llm_providers/glm_direct.py), which
#     POSTs Z.ai's OpenAI-compatible endpoint directly and sends that exact array
#     verbatim. ``litellm_id`` here is the RAW provider model id (no ``zai/``
#     prefix — litellm is bypassed).
#
#   glm-5.1 (provider="litellm") — retained as the litellm-mapped fallback /
#     stand-in (supports_function_calling + supports_reasoning; completes the
#     multi-turn round-trip cleanly). Default of the "glm" set so a flag-free pin
#     stays on the known-good path; glm-5.2 is opt-in by pinning it explicitly.
#
# Both carry an 8192 budget: GLM's default thinking mode bills + consumes the
# completion budget like DeepSeek/gpt-5, so 4096 risks empty-output. The
# thinking-block content shape is collapsed by ``response_text`` (litellm path)
# / the direct client's ``_content_text`` (direct path).
_GLM_PROFILES: list[ModelProfile] = [
    ModelProfile(
        name="glm-5.2",
        litellm_id="glm-5.2",
        tier="reasoning",
        context_window=200000,
        cost_per_1k_input=0.0012,
        cost_per_1k_output=0.0041,
        max_output_tokens=8192,
        provider="direct",
    ),
    ModelProfile(
        name="glm-5.1",
        litellm_id="zai/glm-5.1",
        tier="reasoning",
        context_window=200000,
        cost_per_1k_input=0.0012,
        cost_per_1k_output=0.0041,
        max_output_tokens=8192,
    ),
    *_OPENAI_PROFILES,
]

def _dedupe_by_name(profiles: list[ModelProfile]) -> list[ModelProfile]:
    """First-wins dedupe by ``name`` (LLMService._profiles keys by name, so a
    duplicate name would silently collapse; we keep the first to make the order
    deterministic and the /models list free of dupes)."""
    seen: set[str] = set()
    out: list[ModelProfile] = []
    for p in profiles:
        if p.name not in seen:
            seen.add(p.name)
            out.append(p)
    return out


# The "all" UNION set: every distinct model across the three stacks, PIN-ONLY.
# Used ONLY by the model-A/B sweep so the /models endpoint offers every model
# for the UI dropdown to pin (docs/plans/model_ab_extensive_e2e.plan.md task
# 0.2a). NOT a prod Auto stack — order is openai-first so a stray Auto run on
# this set stays cheap/predictable (first fast == gpt-4o-mini), but the intent
# is that callers PIN a concrete model, never route Auto here.
_ALL_PROFILES: list[ModelProfile] = _dedupe_by_name(
    [*_OPENAI_PROFILES, *_ANTHROPIC_PROFILES, *_DEEPSEEK_PROFILES, *_GLM_PROFILES]
)

# Each entry: (ordered profile list, default_model name). The default is the
# fast-tier steady-state model — it must appear in the list.
_MODEL_PROFILE_SETS: dict[str, tuple[list[ModelProfile], str]] = {
    "openai": (_OPENAI_PROFILES, "gpt-4o-mini"),
    "anthropic": (_ANTHROPIC_PROFILES, "claude-haiku-4-5"),
    "deepseek": (_DEEPSEEK_PROFILES, "deepseek-v4-flash"),
    "glm": (_GLM_PROFILES, "glm-5.1"),
    "all": (_ALL_PROFILES, "gpt-4o-mini"),
}

DEFAULT_MODEL_PROFILE_SET = "openai"


def build_model_registry(
    profile_set: str = DEFAULT_MODEL_PROFILE_SET,
) -> tuple[list[ModelProfile], str]:
    """Return ``(models, default_model)`` for a named profile set.

    The single H2-canonical entry point for the model catalog. An unknown set
    name falls back to the default set (fail-safe: never crash composition on a
    typo'd env var — the byte-identical OpenAI stack is the safe default).
    Returns fresh ``ModelProfile`` copies so callers can't mutate the table.
    """
    models, default_model = _MODEL_PROFILE_SETS.get(
        profile_set, _MODEL_PROFILE_SETS[DEFAULT_MODEL_PROFILE_SET]
    )
    return [m.model_copy(deep=True) for m in models], default_model


def response_text(response: Any) -> str:
    """Normalize an LLM response's content to a plain answer string.

    Provider responses do NOT agree on the shape of ``.content``:
      * OpenAI / Anthropic (non-thinking) → a plain ``str``.
      * DeepSeek V4 (and other reasoning models over LiteLLM) → a **list of
        content blocks**, e.g. ``['', {'type':'thinking',...}, {'type':'text',
        'text':'4'}]`` — the answer lives in the ``text`` blocks and the
        ``thinking`` blocks are model scratchpad that must NOT reach the user.

    A naive ``str(response.content)`` stringifies the whole list (thinking and
    all) into the answer — the user sees ``"['', {'type':'thinking',...}]"``
    instead of ``"4"``. This helper collapses any shape to the answer text by
    reusing LangChain's own block-text extraction (``AIMessage.text``), which
    joins ``text`` blocks and drops ``thinking``/tool blocks. A plain string
    passes through unchanged; ``None``/missing content → ``""``.

    Centralized here (the H2 LLM boundary — the only services/ file allowed to
    import langchain) so every call site in the react loop normalizes
    identically and the provider-shape difference is handled in ONE place.
    """
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    # List-of-blocks (or any non-str): wrap in an AIMessage and reuse the
    # canonical ``.text`` extractor (joins text blocks, drops thinking blocks).
    try:
        from langchain_core.messages import AIMessage

        # ``.text`` is a ``TextAccessor``, not a ``str``. Most providers tolerate
        # it, but Z.ai (GLM-5.2) REJECTS a non-str assistant content echoed back
        # into multi-turn tool history ("content[0].type: cannot be empty"), so
        # coerce to an exact ``str`` here — the single normalization boundary.
        return str(AIMessage(content=content).text)
    except Exception:  # pragma: no cover — defensive; never let normalization throw
        return str(content)


class _DirectChatModel:
    """Boundary shim: adapts a LangChain-free ``LLMProvider`` to the chat-model
    surface the call sites use (``bind_tools`` + ``ainvoke`` → an ``AIMessage``).

    The react loop is built on LangChain message objects (the LangGraph
    ``messages`` channel and checkpointer persist ``AIMessage``/``ToolMessage``/
    ``SystemMessage``), so a direct-call client cannot avoid LangChain at the
    call sites. This shim confines the conversion to ONE place — the H2
    boundary — so the direct provider stays pure and orchestration is unchanged:
      * ``ainvoke`` serializes LangChain messages → OpenAI-shaped dicts (the
        exact multi-turn array including assistant ``tool_calls`` + ``tool``
        results), calls ``provider.acompletion``, and maps the returned
        ``LLMCompletion`` back onto an ``AIMessage`` with ``usage_metadata`` /
        ``response_metadata`` populated, mirroring ChatLiteLLM's return.
      * ``bind_tools`` stores the schemas and returns the model (mirrors
        ``ChatLiteLLM.bind_tools`` — chainable).
    """

    def __init__(
        self,
        provider: Any,
        profile: ModelProfile,
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> None:
        self._provider = provider
        self._profile = profile
        self._tool_schemas = tool_schemas

    def bind_tools(self, tool_schemas: list[dict[str, Any]]) -> _DirectChatModel:
        return _DirectChatModel(
            provider=self._provider,
            profile=self._profile,
            tool_schemas=tool_schemas,
        )

    async def ainvoke(self, messages: list[Any], **kwargs: Any) -> Any:
        from langchain_core.messages import AIMessage

        provider_messages = _ensure_user_first(
            [_lc_message_to_dict(m) for m in messages]
        )
        tools = _normalize_tool_schemas(self._tool_schemas)
        # temperature=0 is the deterministic default unless the model rejects it.
        temperature = 0 if self._profile.supports_temperature else None
        completion = await self._provider.acompletion(
            model=self._profile.litellm_id,
            messages=provider_messages,
            tools=tools,
            temperature=temperature,
            max_tokens=self._profile.max_output_tokens,
        )
        # LangChain's UsageMetadata is strict: it requires ``total_tokens``
        # alongside input/output. The provider reports only prompt/completion, so
        # derive the total here (the loop reads input_tokens/output_tokens for
        # cost; total_tokens just satisfies the AIMessage schema).
        usage_metadata = None
        if completion.usage:
            tin = completion.usage.get("input_tokens", 0)
            tout = completion.usage.get("output_tokens", 0)
            usage_metadata = {
                "input_tokens": tin,
                "output_tokens": tout,
                "total_tokens": tin + tout,
            }
        return AIMessage(
            content=completion.content,
            tool_calls=completion.tool_calls,
            usage_metadata=usage_metadata,
            response_metadata=completion.raw or {},
        )


def _ensure_user_first(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Guarantee the first non-system message is ``user``.

    Z.ai/GLM rejects a conversation whose first non-system turn is ``assistant``
    ("messages parameter is illegal"). On the react-loop synthesis call the
    history is ``system → assistant(tool_calls) → tool…`` (the original human
    task input isn't in the continuation window), so this injects a minimal
    ``user`` turn before the leading assistant turn. A well-formed history (a
    ``user`` already precedes the first ``assistant``) is returned unchanged.
    """
    first_non_system = next(
        (i for i, m in enumerate(messages) if m.get("role") != "system"), None
    )
    if first_non_system is None:
        return messages
    if messages[first_non_system].get("role") == "user":
        return messages
    # First non-system turn is assistant/tool → inject a user turn before it.
    # The original task input isn't in this continuation window, but the tool
    # results that follow carry the evidence; this directive tells the model to
    # use them and answer (vs a bare "Continue." which made GLM report it had no
    # task context). Generic enough to be task-agnostic at this boundary.
    placeholder = {
        "role": "user",
        "content": (
            "Use the tool results above to complete the task and give the final "
            "answer."
        ),
    }
    return messages[:first_non_system] + [placeholder] + messages[first_non_system:]


def _normalize_tool_schemas(
    schemas: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """Wrap flat tool schemas in the OpenAI ``{"type":"function","function":...}``
    envelope the provider expects.

    The tool registry (services/tools/registry.py:get_schemas) emits the flat
    LangChain shape ``{"name","description","parameters"}`` — ChatLiteLLM
    normalizes it before sending, but the direct client talks raw OpenAI-style,
    and Z.ai 400s without the envelope ("tools[0].type:type cannot be empty").
    Idempotent: a schema already carrying ``type``/``function`` passes through.
    """
    if not schemas:
        return None
    out: list[dict[str, Any]] = []
    for schema in schemas:
        if "function" in schema or schema.get("type") == "function":
            out.append(schema)
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": schema.get("name", ""),
                    "description": schema.get("description", ""),
                    "parameters": schema.get("parameters", {}),
                },
            }
        )
    return out


def _lc_message_to_dict(message: Any) -> dict[str, Any]:
    """Serialize a LangChain message to the OpenAI chat-completion dict shape.

    Inverse of ``LLMService.invoke``'s dict→LC mapping. Handles the multi-turn
    tool case LiteLLM mangled: an ``AIMessage`` carrying ``tool_calls`` becomes
    an ``assistant`` turn with OpenAI-shaped ``tool_calls`` (function name +
    JSON-string arguments), and a ``ToolMessage`` becomes a ``tool`` turn with
    its ``tool_call_id``.
    """
    import json

    from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

    if isinstance(message, SystemMessage):
        return {"role": "system", "content": response_text(message)}
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": getattr(message, "tool_call_id", ""),
            "content": response_text(message),
        }
    if isinstance(message, AIMessage):
        out: dict[str, Any] = {"role": "assistant", "content": response_text(message)}
        tool_calls = getattr(message, "tool_calls", None) or []
        if tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": json.dumps(tc.get("args", {})),
                    },
                }
                for tc in tool_calls
            ]
        return out
    # Default: anything else (HumanMessage and bare strings) is a user turn.
    return {"role": "user", "content": response_text(message)}


class LLMService:
    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._profiles: dict[str, ModelProfile] = {m.name: m for m in config.models}

    def get_profile(self, name: str) -> ModelProfile:
        if name not in self._profiles:
            raise KeyError(f"Model profile '{name}' not found. Available: {list(self._profiles.keys())}")
        return self._profiles[name]

    def get_default_profile(self) -> ModelProfile:
        return self.get_profile(self._config.default_model)

    def get_llm(self, profile: ModelProfile) -> Any:
        """Returns the chat model for a profile.

        Branches on ``profile.provider`` (the routing trigger):
          * ``"direct"``  — a model LiteLLM cannot serve (e.g. glm-5.2). Build the
            direct REST client and wrap it in ``_DirectChatModel`` so the call
            sites (.bind_tools / .ainvoke, reading .content/.tool_calls/usage)
            are unchanged. This is the only place LangChain meets the direct
            client; the client itself is LangChain-free.
          * ``"litellm"`` — the default: LiteLLM's ChatLiteLLM wrapper (below).
        """
        if profile.provider == "direct":
            from services.llm_providers import get_direct_provider

            return _DirectChatModel(
                provider=get_direct_provider(profile), profile=profile
            )

        from langchain_litellm import ChatLiteLLM

        # NOTE: ``streaming=True`` here means token usage does NOT reach the
        # runtime adapter's ``on_chat_model_end`` event (the .ainvoke return
        # value carries ``usage_metadata`` — which is why cost on the canonical
        # STEP_EXECUTED record is correct — but the streamed end callback the
        # wire bridge observes does not). ``stream_options={"include_usage":...}``
        # is a no-op: langchain_litellm already defaults it. The durable token
        # carrier in the trace is the relayed STEP_EXECUTED span (publisher maps
        # its tokens to native ``usage``); see the curated-view note in
        # middleware/sidecars/black_box_to_telemetry.py.
        # ``temperature=0`` is the deterministic default the agent relies on, but
        # some models (claude-opus-4-8) deprecated the parameter and 400 when one
        # is sent — surfacing as an empty answer downstream. Omit it for those
        # (``supports_temperature=False``) so they fall back to the provider
        # default; every other model keeps temperature=0.
        # ``max_tokens`` is the completion budget. Reasoning models spend
        # ``thinking`` tokens against it before the visible answer; a budget too
        # small can be wholly consumed by reasoning, yielding an empty answer
        # (deepseek-v4-flash / gpt-5 at 4096). Per-profile ``max_output_tokens``
        # lets the reasoning tier carry more headroom (default 4096).
        kwargs: dict[str, Any] = {
            "model": profile.litellm_id,
            "max_tokens": profile.max_output_tokens,
            "streaming": True,
        }
        if profile.supports_temperature:
            kwargs["temperature"] = 0
        return ChatLiteLLM(**kwargs)

    async def invoke(
        self,
        profile: ModelProfile,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        """Invoke LLM with the given profile and messages."""
        llm = self.get_llm(profile)
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        logger.info(
            "Invoking %s (%s tier)",
            profile.name,
            profile.tier,
            extra={"model": profile.name, "tier": profile.tier},
        )
        return await llm.ainvoke(lc_messages, **kwargs)

    async def invoke_with_tools(
        self,
        profile: ModelProfile,
        messages: list[Any],
        tool_schemas: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Invoke LLM with LangChain messages and optional tool binding.

        Unlike ``invoke()``, this accepts pre-built LangChain message objects
        directly (including AIMessage with tool_calls and ToolMessage) so the
        full conversation history flows to the model.
        """
        llm = self.get_llm(profile)
        if tool_schemas:
            llm = llm.bind_tools(tool_schemas)

        logger.info(
            "Invoking %s (%s tier) with %d messages, %d tools",
            profile.name,
            profile.tier,
            len(messages),
            len(tool_schemas or []),
            extra={"model": profile.name, "tier": profile.tier},
        )
        return await llm.ainvoke(messages, **kwargs)
