"""L1 Deterministic: Tests for services/base_config.py.

Pure TDD (Red-Green-Refactor). Tests ModelProfile and AgentConfig
defaults, validation, roundtrip.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.base_config import AgentConfig, ModelProfile, compaction_trigger_tokens


class TestModelProfile:
    def test_valid_construction(self):
        mp = ModelProfile(
            name="gpt-4o-mini",
            litellm_id="openai/gpt-4o-mini",
            tier="fast",
            context_window=128000,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
        )
        assert mp.name == "gpt-4o-mini"
        assert mp.tier == "fast"

    def test_median_latency_default(self):
        mp = ModelProfile(
            name="gpt-4o",
            litellm_id="openai/gpt-4o",
            tier="capable",
            context_window=128000,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
        )
        assert mp.median_latency_ms == 1000

    def test_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            ModelProfile(name="x", tier="fast")  # type: ignore[call-arg]

    def test_roundtrip_json(self):
        mp = ModelProfile(
            name="claude-3-sonnet",
            litellm_id="anthropic/claude-3-sonnet",
            tier="capable",
            context_window=200000,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            median_latency_ms=2000,
        )
        restored = ModelProfile.model_validate_json(mp.model_dump_json())
        assert restored == mp


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.max_steps == 20
        assert cfg.max_cost_usd == 1.0
        assert cfg.default_model == "gpt-4o-mini"
        assert cfg.models == []
        assert cfg.tool_output_offload_threshold_chars == 4000
        assert cfg.tool_output_preview_chars == 400
        assert cfg.tool_result_history_limit == 100
        assert cfg.delegation_max_cost_usd == 0.5
        assert cfg.delegation_max_calls_per_task == 4

    def test_override_defaults(self):
        mp = ModelProfile(
            name="gpt-4o",
            litellm_id="openai/gpt-4o",
            tier="capable",
            context_window=128000,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
        )
        cfg = AgentConfig(max_steps=50, max_cost_usd=5.0, models=[mp])
        assert cfg.max_steps == 50
        assert len(cfg.models) == 1
        assert cfg.models[0].name == "gpt-4o"

    def test_roundtrip_json(self):
        cfg = AgentConfig(max_steps=10, max_cost_usd=0.5)
        restored = AgentConfig.model_validate_json(cfg.model_dump_json())
        assert restored == cfg


# ════════════════════════════════════════════════════════════════════════════
# C1 Phase 4 — the 7 context_* fields (design §9 table).
#
# Failure-first (Protocol A): the headline guards are the OFF defaults —
# byte-identical-when-off is the prod-safety invariant the impl plan asserts
# (§9 "with the master flag False, both seams early-return"). Without the
# field pin, a default flip silently turns compaction on for every consumer.
# ════════════════════════════════════════════════════════════════════════════


class TestC1ContextDefaults:
    def test_master_flag_default_off(self):
        """The master compaction flag MUST default OFF — every other
        context_* field is conditioned on this. A stray ``True`` default
        would silently activate compaction across every running deployment."""
        cfg = AgentConfig()
        assert cfg.context_compact_messages_enabled is False

    def test_trigger_fraction_default(self):
        cfg = AgentConfig()
        assert cfg.context_compact_trigger_fraction == 0.6

    def test_observation_clear_fraction_default(self):
        cfg = AgentConfig()
        assert cfg.context_observation_clear_fraction == 0.3

    def test_keep_last_k_default(self):
        cfg = AgentConfig()
        assert cfg.context_keep_last_k == 10

    def test_mask_after_steps_default_is_b1r_ablated_optimum(self):
        """M=10 is the §B1-R R1 ablated optimum — pinned so an off-by-one in
        a future patch doesn't silently shift the ablation point."""
        cfg = AgentConfig()
        assert cfg.context_mask_after_steps == 10

    def test_cooldown_steps_default(self):
        cfg = AgentConfig()
        assert cfg.context_compact_cooldown_steps == 5

    def test_constraint_reinject_default_is_zero_tail_off(self):
        """N=0 means the persisted-tail floor is OFF (§5.2 / §9 footnote).
        The opt-in tail puts constraint text on the checkpointer's privileged
        store (§7.3 caveat), so the ship default keeps it out of the
        checkpoint entirely."""
        cfg = AgentConfig()
        assert cfg.context_constraint_reinject_turns == 0

    def test_legacy_trajectory_threshold_preserved(self):
        """C1 must NOT touch the legacy trajectory_compaction_token_threshold —
        the existing trajectory path is a separate seam."""
        cfg = AgentConfig()
        assert cfg.trajectory_compaction_token_threshold == 3000


class TestCompactionTriggerTokens:
    """The pure helper (design §9): ``window * fraction`` floored to int."""

    def test_returns_int(self):
        assert isinstance(compaction_trigger_tokens(128_000, 0.6), int)

    def test_default_fraction_against_128k(self):
        # 128_000 * 0.6 == 76800 exactly.
        assert compaction_trigger_tokens(128_000, 0.6) == 76_800

    def test_default_fraction_against_200k(self):
        # 200_000 * 0.6 == 120000 exactly.
        assert compaction_trigger_tokens(200_000, 0.6) == 120_000

    def test_zero_fraction_returns_floor_one(self):
        """A degenerate fraction must never disable the trigger by returning
        0 — the WRITE seam compares ``tokens >= trigger`` and a 0 trigger
        would compact on every step. Floor at 1 keeps the trigger live."""
        assert compaction_trigger_tokens(128_000, 0.0) >= 1

    def test_zero_window_returns_floor_one(self):
        """Symmetric floor: an unconfigured ModelProfile.context_window of 0
        must NOT collapse the trigger to 0."""
        assert compaction_trigger_tokens(0, 0.6) >= 1

    def test_full_fraction(self):
        assert compaction_trigger_tokens(100, 1.0) == 100

    def test_deterministic(self):
        """Pure helper: 10 calls identical."""
        outs = {compaction_trigger_tokens(128_000, 0.6) for _ in range(10)}
        assert len(outs) == 1
