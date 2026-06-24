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
