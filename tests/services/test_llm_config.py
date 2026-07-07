"""L2 Reproducible: Tests for services/llm_config.py.

Contract-driven TDD with mock providers. Tests LLM factory creation,
model profile lookup, and the invoke wrapper. No live LLM calls.
"""

from __future__ import annotations

import pytest

from services.base_config import AgentConfig, ModelProfile
from services.llm_config import (
    DEFAULT_MODEL_PROFILE_SET,
    LLMService,
    build_model_registry,
    response_text,
)


def _fast_profile():
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _capable_profile():
    return ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    )


class TestLLMService:
    def test_get_profile_by_name(self):
        cfg = AgentConfig(models=[_fast_profile(), _capable_profile()])
        svc = LLMService(config=cfg)
        profile = svc.get_profile("gpt-4o-mini")
        assert profile.tier == "fast"

    def test_get_profile_missing_raises(self):
        cfg = AgentConfig(models=[_fast_profile()])
        svc = LLMService(config=cfg)
        with pytest.raises(KeyError):
            svc.get_profile("nonexistent-model")

    def test_get_default_profile(self):
        cfg = AgentConfig(
            default_model="gpt-4o-mini",
            models=[_fast_profile(), _capable_profile()],
        )
        svc = LLMService(config=cfg)
        profile = svc.get_default_profile()
        assert profile.name == "gpt-4o-mini"

    def test_get_llm_returns_chat_model(self):
        cfg = AgentConfig(models=[_fast_profile()])
        svc = LLMService(config=cfg)
        llm = svc.get_llm(_fast_profile())
        assert llm is not None

    def test_get_llm_sends_temperature_zero_by_default(self):
        """The deterministic default: a normal model gets ``temperature=0``."""
        cfg = AgentConfig(models=[_fast_profile()])
        svc = LLMService(config=cfg)
        llm = svc.get_llm(_fast_profile())
        assert llm.temperature == 0

    def test_get_llm_omits_temperature_when_unsupported(self):
        """Regression (Opus-4.8 empty-output defect, 2026-06-25): a model with
        ``supports_temperature=False`` must NOT receive a ``temperature`` request
        param. claude-opus-4-8 deprecated it and 400s when one is sent, which the
        runtime swallowed into the empty-output placeholder ($0 / 0 tokens). With
        the param omitted, ChatLiteLLM leaves ``temperature`` at its ``None``
        default so litellm sends no temperature field at all."""
        no_temp = ModelProfile(
            name="claude-opus-4-8",
            litellm_id="anthropic/claude-opus-4-8",
            tier="reasoning",
            context_window=1_000_000,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.025,
            supports_temperature=False,
        )
        cfg = AgentConfig(models=[no_temp])
        svc = LLMService(config=cfg)
        llm = svc.get_llm(no_temp)
        assert llm.temperature is None

    def test_registry_opus_profile_marks_temperature_unsupported(self):
        """The shipped anthropic/all registries must carry the Opus capability
        flag — otherwise the live A/B Opus arm regresses to empty output."""
        for set_name in ("anthropic", "all"):
            models, _ = build_model_registry(set_name)
            opus = next(m for m in models if m.name == "claude-opus-4-8")
            assert opus.supports_temperature is False
            # Sibling Anthropic tiers keep temperature (deterministic default).
            sonnet = next(m for m in models if m.name == "claude-sonnet-4-6")
            assert sonnet.supports_temperature is True

    def test_registry_gpt5_family_marks_temperature_unsupported(self):
        """gpt-5 / gpt-5-mini reject temperature=0 (litellm UnsupportedParams) —
        same empty-output failure class as Opus. Both must carry the flag so a
        pin to either doesn't regress; gpt-4o keeps the deterministic default."""
        for set_name in ("anthropic", "all"):
            models, _ = build_model_registry(set_name)
            for name in ("gpt-5", "gpt-5-mini"):
                prof = next(m for m in models if m.name == name)
                assert prof.supports_temperature is False, name
            gpt4o = next(m for m in models if m.name == "gpt-4o")
            assert gpt4o.supports_temperature is True

    def test_get_llm_uses_profile_max_output_tokens(self):
        """The completion budget comes from the profile (default 4096), and a
        reasoning profile carrying a larger ``max_output_tokens`` is honored —
        the fix for reasoning-budget exhaustion (empty answer when thinking
        tokens consume the whole budget)."""
        default_prof = _fast_profile()
        cfg = AgentConfig(models=[default_prof])
        svc = LLMService(config=cfg)
        assert svc.get_llm(default_prof).max_tokens == 4096

        big = ModelProfile(
            name="reasoner",
            litellm_id="anthropic/claude-opus-4-8",
            tier="reasoning",
            context_window=1_000_000,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.025,
            supports_temperature=False,
            max_output_tokens=8192,
        )
        cfg2 = AgentConfig(models=[big])
        assert LLMService(config=cfg2).get_llm(big).max_tokens == 8192

    def test_registry_reasoning_models_carry_larger_budget(self):
        """Reasoning/verbose-reasoning models must ship the raised budget so a
        live pin doesn't regress to empty output."""
        models, _ = build_model_registry("all")
        by = {m.name: m for m in models}
        for name in ("claude-opus-4-8", "gpt-5", "gpt-5-mini", "deepseek-v4-flash"):
            assert by[name].max_output_tokens == 8192, name
        # Non-reasoning models keep the 4096 default.
        for name in ("gpt-4o", "gpt-4o-mini", "claude-haiku-4-5", "claude-sonnet-4-6"):
            assert by[name].max_output_tokens == 4096, name

    def test_get_llm_streams(self):
        """The model streams (drives the runtime token deltas). Token *usage*
        does not ride the streamed end event — it is carried on the canonical
        STEP_EXECUTED record and relayed as native ``usage`` (see the
        curated-view note in black_box_to_telemetry.py); a stream_options
        toggle here is a no-op (langchain_litellm already defaults it)."""
        cfg = AgentConfig(models=[_fast_profile()])
        svc = LLMService(config=cfg)
        llm = svc.get_llm(_fast_profile())
        assert getattr(llm, "streaming", False) is True


class _Resp:
    """Minimal stand-in for an LLM response carrying a ``.content`` attribute."""

    def __init__(self, content):
        self.content = content


class TestResponseText:
    """Provider-content normalization (the DeepSeek list-of-blocks fix).

    Failure path FIRST (TAP-4): the dangerous case is a DeepSeek-shaped LIST of
    blocks being stringified into the user's answer (thinking scratchpad and
    all). ``response_text`` must collapse it to the answer text.
    """

    def test_deepseek_list_of_blocks_returns_answer_text_only(self):
        # The exact shape DeepSeek V4 Flash returned in the pre-deploy smoke:
        # a leading '' + thinking blocks + the answer in text blocks.
        content = [
            "",
            {"type": "thinking", "thinking": "We need to answer"},
            {"type": "text", "text": "The answer is "},
            {"type": "text", "text": "4"},
        ]
        out = response_text(_Resp(content))
        assert out == "The answer is 4"
        assert "thinking" not in out  # scratchpad must NOT reach the user

    def test_plain_string_passes_through(self):
        assert response_text(_Resp("just a plain answer")) == "just a plain answer"

    def test_none_content_is_empty_string(self):
        assert response_text(_Resp(None)) == ""

    def test_empty_list_is_empty_string(self):
        assert response_text(_Resp([])) == ""

    def test_thinking_only_list_yields_empty_not_stringified(self):
        # A response that is ALL thinking (no text block) must NOT stringify the
        # dict list into the answer — it yields "" (the caller treats empty as
        # "no answer", which is correct).
        content = [{"type": "thinking", "thinking": "hmm"}]
        out = response_text(_Resp(content))
        assert "{" not in out and "thinking" not in out

    def test_bare_string_argument_also_works(self):
        # Defensive: passed a bare string instead of a response object.
        assert response_text("hello") == "hello"

    def test_list_content_returns_exact_str_not_text_accessor(self):
        # GLM-5.2/Z.ai REJECTS a non-str assistant content echoed back into the
        # multi-turn tool history ("messages[..].content[0].type: cannot be
        # empty"). LangChain's ``AIMessage(...).text`` is a ``TextAccessor``, not
        # a ``str`` — leaning providers (OpenAI/Anthropic/DeepSeek) tolerate it,
        # Z.ai does not. ``response_text`` MUST return an exact ``str`` so the
        # value re-sent in history is a plain string for every provider.
        out = response_text(_Resp([{"type": "text", "text": "answer"}]))
        assert type(out) is str, f"expected exact str, got {type(out).__name__}"
        out_thinking = response_text(_Resp([{"type": "thinking", "thinking": "x"}]))
        assert type(out_thinking) is str


def _first_tier(models, tier):
    """First profile of a tier — the one the router's first-match would pick."""
    return next((m for m in models if m.tier == tier), None)


class TestModelRegistry:
    """H2 central registry + the order-is-a-safety-contract invariant.

    Failure/invariant assertions first (TAP-4): a wrong first-match per tier is
    the dangerous case — Auto would silently route to the wrong model.
    """

    # ── Rejection / fail-safe paths first ────────────────────────────────
    def test_unknown_set_falls_back_to_default_not_crash(self):
        models, default_model = build_model_registry("does-not-exist")
        baseline_models, baseline_default = build_model_registry(
            DEFAULT_MODEL_PROFILE_SET
        )
        assert default_model == baseline_default
        assert [m.name for m in models] == [m.name for m in baseline_models]

    def test_default_set_is_openai_byte_identical(self):
        """Flag-off path is a no-op: first fast == gpt-4o-mini, first capable
        == gpt-4o, and a gpt-* model wins every first-match."""
        models, default_model = build_model_registry("openai")
        assert default_model == "gpt-4o-mini"
        assert _first_tier(models, "fast").name == "gpt-4o-mini"
        assert _first_tier(models, "capable").name == "gpt-4o"
        assert _first_tier(models, "fast").name.startswith("gpt-")

    def test_registry_copies_are_isolated(self):
        """Callers can't mutate the shared table through a returned profile."""
        models_a, _ = build_model_registry("anthropic")
        models_a[0].name = "MUTATED"
        models_b, _ = build_model_registry("anthropic")
        assert models_b[0].name != "MUTATED"

    # ── Acceptance: the 3-tier anthropic order contract ──────────────────
    def test_anthropic_set_three_tier_order_contract(self):
        models, default_model = build_model_registry("anthropic")
        assert default_model == "claude-haiku-4-5"
        assert _first_tier(models, "fast").name == "claude-haiku-4-5"
        assert _first_tier(models, "capable").name == "claude-sonnet-4-6"
        assert _first_tier(models, "reasoning").name == "claude-opus-4-8"

    def test_anthropic_set_no_gpt_wins_a_first_match(self):
        """gpt-* are registered (pin-only) but must never win Auto first-match."""
        models, _ = build_model_registry("anthropic")
        for tier in ("fast", "capable", "reasoning"):
            first = _first_tier(models, tier)
            if first is not None:
                assert not first.name.startswith("gpt-"), (
                    f"a gpt-* model won the {tier} first-match under anthropic"
                )

    def test_litellm_ids_dispatch_by_provider_prefix(self):
        """Provider dispatch is by litellm_id prefix (no call-site change)."""
        models, _ = build_model_registry("anthropic")
        by_name = {m.name: m for m in models}
        assert by_name["claude-opus-4-8"].litellm_id.startswith("anthropic/")
        assert by_name["gpt-4o"].litellm_id.startswith("openai/")

    # ── Fireworks host set (ADR-0019) ────────────────────────────────────
    def test_fireworks_set_default_and_lead_profile(self):
        """The ``fireworks`` set exists, defaults to the GLM-5.2 lead, and the
        lead is a direct-provider profile carrying the Fireworks wire model id
        (FR-5/FR-6: the pin reaches a Fireworks-host profile, no string-munging
        in the caller)."""
        models, default_model = build_model_registry("fireworks")
        assert default_model == "glm-5.2-fireworks"
        by_name = {m.name: m for m in models}
        lead = by_name["glm-5.2-fireworks"]
        assert lead.provider == "direct"
        # Fireworks encodes the version dot as ``p``: glm-5.2 → glm-5p2 (the bare
        # ``glm-5.2`` slug 404s — confirmed live 2026-07-06).
        assert lead.litellm_id == "accounts/fireworks/models/glm-5p2"

    def test_fireworks_set_carries_cross_family_candidates(self):
        """FR-7: the set offers the cross-family reasoning candidates to screen —
        each a direct profile with a Fireworks wire id. These are the models the
        account's serverless catalog actually serves (confirmed 2026-07-06); the
        originally-guessed deepseek-r1 / qwen3 / nemotron are dedicated-only."""
        models, _ = build_model_registry("fireworks")
        by_name = {m.name: m for m in models}
        for cand in (
            "deepseek-v4-pro-fireworks",
            "kimi-k2.6-fireworks",
            "gpt-oss-120b-fireworks",
        ):
            assert cand in by_name, f"missing screening candidate {cand}"
            assert by_name[cand].provider == "direct"
            assert by_name[cand].litellm_id.startswith("accounts/fireworks/models/")

    def test_fireworks_profiles_route_to_fireworks_not_zai(self, monkeypatch):
        """Every ``-fireworks`` profile in the set dispatches to the Fireworks
        adapter (the ordering guard, exercised through the real registry)."""
        from services.llm_providers import get_direct_provider
        from services.llm_providers.fireworks_direct import FireworksDirectProvider

        monkeypatch.setenv("FIREWORKS_API_KEY", "fw-k")
        models, _ = build_model_registry("fireworks")
        for m in models:
            if m.name.endswith("-fireworks"):
                provider = get_direct_provider(m)
                assert isinstance(provider, FireworksDirectProvider), (
                    f"{m.name} did not route to Fireworks"
                )

    # ── Acceptance: the DeepSeek V4 stack (Flash fast+capable / Pro reasoning) ──
    def test_deepseek_set_order_contract(self):
        """Flash fills fast AND capable (same litellm_id, distinct name); Pro is
        the reasoning tier. Order is the safety contract — first-match per tier."""
        models, default_model = build_model_registry("deepseek")
        assert default_model == "deepseek-v4-flash"
        assert _first_tier(models, "fast").name == "deepseek-v4-flash"
        assert _first_tier(models, "capable").name == "deepseek-v4-flash-capable"
        assert _first_tier(models, "reasoning").name == "deepseek-v4-pro"

    def test_deepseek_two_flash_profiles_share_litellm_id_distinct_names(self):
        """The fast + capable Flash profiles MUST share litellm_id but have
        distinct names (LLMService._profiles keys by name — names would collide
        and the pin lookup needs uniqueness)."""
        models, _ = build_model_registry("deepseek")
        flash = [m for m in models if m.name.startswith("deepseek-v4-flash")]
        assert {m.name for m in flash} == {
            "deepseek-v4-flash",
            "deepseek-v4-flash-capable",
        }
        assert {m.litellm_id for m in flash} == {"deepseek/deepseek-v4-flash"}
        # Distinct names => no key collision when fed to LLMService.
        cfg = AgentConfig(default_model="deepseek-v4-flash", models=models)
        svc = LLMService(config=cfg)
        assert svc.get_profile("deepseek-v4-flash").tier == "fast"
        assert svc.get_profile("deepseek-v4-flash-capable").tier == "capable"

    def test_deepseek_set_no_gpt_wins_a_first_match(self):
        """gpt-* are pin-only under deepseek too — never win Auto first-match."""
        models, _ = build_model_registry("deepseek")
        for tier in ("fast", "capable", "reasoning"):
            first = _first_tier(models, tier)
            if first is not None:
                assert not first.name.startswith("gpt-"), (
                    f"a gpt-* model won the {tier} first-match under deepseek"
                )

    def test_deepseek_litellm_ids_dispatch_deepseek_prefix(self):
        models, _ = build_model_registry("deepseek")
        by_name = {m.name: m for m in models}
        assert by_name["deepseek-v4-flash"].litellm_id.startswith("deepseek/")
        assert by_name["deepseek-v4-pro"].litellm_id.startswith("deepseek/")

    # ── The GLM-5 stack (research #1 tool-caller tier; pin-only, zai provider) ──
    # Pinned to glm-5.1, NOT glm-5.2: ``zai/glm-5.2`` is absent from litellm's zai
    # model map, so the multi-turn tool loop sends a message array Z.ai rejects
    # ("messages parameter is illegal"). glm-5.1 IS mapped (tool_use + reasoning)
    # and completes the round-trip. See _GLM_PROFILES comment in llm_config.py.
    def test_glm_set_resolves_glm51_as_default(self):
        models, default_model = build_model_registry("glm")
        assert default_model == "glm-5.1"
        by_name = {m.name: m for m in models}
        assert "glm-5.1" in by_name
        # zai provider dispatch by litellm_id prefix (no call-site change). Must be
        # a litellm-mapped zai model id, not glm-5.2 (the unmapped id that fails).
        assert by_name["glm-5.1"].litellm_id == "zai/glm-5.1"
        # GLM default thinking mode inflates output — carries a larger budget so a
        # verbose trace can't consume the whole budget and return an empty answer.
        assert by_name["glm-5.1"].max_output_tokens >= 8192

    def test_all_set_includes_glm51(self):
        models, _ = build_model_registry("all")
        assert "glm-5.1" in {m.name for m in models}

    # ── GLM-5.2 via the direct-call extension (LiteLLM can't serve it) ──────
    def test_glm52_routed_through_direct_provider(self):
        """glm-5.2 is registered with provider="direct" — the routing trigger
        that sends it to the direct REST client instead of LiteLLM. Its
        litellm_id is the RAW provider id (no zai/ prefix; LiteLLM is bypassed)."""
        for set_name in ("glm", "all"):
            models, _ = build_model_registry(set_name)
            by_name = {m.name: m for m in models}
            assert "glm-5.2" in by_name, set_name
            assert by_name["glm-5.2"].provider == "direct"
            assert by_name["glm-5.2"].litellm_id == "glm-5.2"
            # Same thinking-budget headroom as glm-5.1 (avoid empty-output).
            assert by_name["glm-5.2"].max_output_tokens >= 8192

    def test_glm51_stays_litellm_fallback(self):
        """glm-5.1 (the LiteLLM-mapped stand-in) is retained as the default and
        keeps provider="litellm" — both GLM rows are pin-selectable."""
        models, default_model = build_model_registry("glm")
        by_name = {m.name: m for m in models}
        assert default_model == "glm-5.1"
        assert by_name["glm-5.1"].provider == "litellm"
        assert by_name["glm-5.1"].litellm_id == "zai/glm-5.1"

    def test_all_other_models_default_to_litellm_provider(self):
        """The ``provider="direct"`` field is opt-in for KNOWN direct hosts only:
        the Z.ai ``glm-5.2`` row and the Fireworks ``-fireworks`` rows (ADR-0019).
        Every other profile stays "litellm", so flag-off / existing behavior is
        byte-identical. (The exclusion list is explicit — a NEW model silently
        defaulting to "direct" would fail here, which is the guard's point.)"""
        for set_name in ("openai", "anthropic", "deepseek", "all"):
            models, _ = build_model_registry(set_name)
            for m in models:
                # Known direct-host profiles are legitimately provider="direct".
                if m.name == "glm-5.2" or m.name.endswith("-fireworks"):
                    assert m.provider == "direct", f"{set_name}:{m.name} lost direct"
                    continue
                assert m.provider == "litellm", f"{set_name}:{m.name}"

    def test_get_llm_returns_direct_chat_model_for_glm52(self, monkeypatch):
        """get_llm branches on provider: a direct profile yields the boundary
        shim (_DirectChatModel), a litellm profile yields ChatLiteLLM."""
        from services.llm_config import _DirectChatModel

        monkeypatch.setenv("GLM_API_KEY", "test-key")
        models, _ = build_model_registry("glm")
        by_name = {m.name: m for m in models}
        svc = LLMService(config=AgentConfig(default_model="glm-5.1", models=models))
        assert isinstance(svc.get_llm(by_name["glm-5.2"]), _DirectChatModel)
        # glm-5.1 still goes through ChatLiteLLM (litellm path unchanged).
        litellm_model = svc.get_llm(by_name["glm-5.1"])
        assert type(litellm_model).__name__ == "ChatLiteLLM"

    # ── The "all" union meta-set (A/B UI-pin sweep — every model on /models) ──
    def test_all_set_lists_every_distinct_model_no_dupes(self):
        """The /models endpoint under MODEL_PROFILE_SET=all must offer every
        distinct model so the dropdown can pin each — and carry NO duplicate
        names (LLMService keys by name)."""
        models, default_model = build_model_registry("all")
        names = [m.name for m in models]
        assert len(names) == len(set(names)), f"duplicate names in 'all': {names}"
        # every concrete model from all three stacks is present
        for expected in (
            "gpt-4o-mini",
            "gpt-4o",
            "claude-haiku-4-5",
            "claude-sonnet-4-6",
            "claude-opus-4-8",
            "deepseek-v4-flash",
            "deepseek-v4-flash-capable",
            "deepseek-v4-pro",
        ):
            assert expected in names, f"'all' set missing {expected}"
        assert default_model == "gpt-4o-mini"  # cheap, predictable

    def test_all_set_pins_resolve_across_providers(self):
        """Each provider's model is pin-resolvable via LLMService under 'all'."""
        models, default_model = build_model_registry("all")
        svc = LLMService(config=AgentConfig(default_model=default_model, models=models))
        assert svc.get_profile("claude-opus-4-8").litellm_id.startswith("anthropic/")
        assert svc.get_profile("deepseek-v4-pro").litellm_id.startswith("deepseek/")
        assert svc.get_profile("gpt-4o").litellm_id.startswith("openai/")
