"""L1 Deterministic: Tests for services/base_config.py.

Pure TDD (Red-Green-Refactor). Tests ModelProfile and AgentConfig
defaults, validation, roundtrip.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.base_config import AgentConfig, ModelProfile


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
