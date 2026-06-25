"""ModelProfile registry and ChatLiteLLM factory (H2 pattern).

Provides LLM access via LiteLLM's LangChain-compatible wrapper.
This is the only file in services/ allowed to import from langchain.
"""

from __future__ import annotations

import logging
from typing import Any

from services.base_config import AgentConfig, ModelProfile

logger = logging.getLogger("services.llm_config")


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
    ),
    ModelProfile(
        name="gpt-5-mini",
        litellm_id="openai/gpt-5-mini",
        tier="fast",
        context_window=400000,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.002,
    ),
    ModelProfile(
        name="gpt-5",
        litellm_id="openai/gpt-5",
        tier="capable",
        context_window=400000,
        cost_per_1k_input=0.00125,
        cost_per_1k_output=0.010,
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
    ),
    ModelProfile(
        name="deepseek-v4-pro",
        litellm_id="deepseek/deepseek-v4-pro",
        tier="reasoning",
        context_window=1000000,
        cost_per_1k_input=0.000435,
        cost_per_1k_output=0.00087,
    ),
    *_OPENAI_PROFILES,
]

# Each entry: (ordered profile list, default_model name). The default is the
# fast-tier steady-state model — it must appear in the list.
_MODEL_PROFILE_SETS: dict[str, tuple[list[ModelProfile], str]] = {
    "openai": (_OPENAI_PROFILES, "gpt-4o-mini"),
    "anthropic": (_ANTHROPIC_PROFILES, "claude-haiku-4-5"),
    "deepseek": (_DEEPSEEK_PROFILES, "deepseek-v4-flash"),
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

        return AIMessage(content=content).text
    except Exception:  # pragma: no cover — defensive; never let normalization throw
        return str(content)


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
        """Returns a ChatLiteLLM instance for the given profile."""
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
        return ChatLiteLLM(
            model=profile.litellm_id,
            temperature=0,
            max_tokens=4096,
            streaming=True,
        )

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
