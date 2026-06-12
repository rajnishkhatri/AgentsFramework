"""L2 Reproducible: Tests for services/llm_config.py.

Contract-driven TDD with mock providers. Tests LLM factory creation,
model profile lookup, and the invoke wrapper. No live LLM calls.
"""

from __future__ import annotations

import pytest

from services.base_config import AgentConfig, ModelProfile
from services.llm_config import LLMService


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

    def test_get_llm_requests_usage_in_stream(self):
        """Phase 3 token-usage fix: ``streaming=True`` suppresses the final
        message's ``usage_metadata`` unless the provider is asked to emit a
        usage chunk. Setting ``stream_options={'include_usage': True}`` makes
        LiteLLM request it, so the aggregated streamed AIMessage carries
        ``usage_metadata`` — which ``_extract_usage`` reads and the bridge folds
        into the ``llm.call`` generation's native ``usage_details``."""
        cfg = AgentConfig(models=[_fast_profile()])
        svc = LLMService(config=cfg)
        llm = svc.get_llm(_fast_profile())
        assert getattr(llm, "streaming", False) is True
        assert getattr(llm, "stream_options", None) == {"include_usage": True}
