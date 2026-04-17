"""L2 tests for ``meta.CodeReviewerAgentTest.env_settings``.

Failure paths first (TAP-4): the missing-var fallback and unknown-id
fallback are tested before the happy path so the defensive guards
cannot silently regress.
"""

from __future__ import annotations

import logging

import pytest

from meta.CodeReviewerAgentTest.env_settings import (
    EnvSettings,
    reviewer_profile_from_env,
)
from services.base_config import default_fast_profile


# ── Failure paths ──────────────────────────────────────────────────


def test_missing_env_var_falls_back_to_default_fast_profile(monkeypatch):
    """Unset env var must NOT raise -- we fall back to the canonical default."""
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.setattr(EnvSettings, "model_config",
                        {**EnvSettings.model_config, "env_file": "/nonexistent.env"})

    profile = reviewer_profile_from_env("MODEL_NAME")
    expected = default_fast_profile()
    assert profile.litellm_id == expected.litellm_id
    assert profile.tier == expected.tier


def test_unknown_litellm_id_emits_warning_and_returns_defensive_profile(
    monkeypatch, caplog
):
    monkeypatch.setenv("MODEL_NAME", "fake_provider/unknown-model-9000")
    monkeypatch.setattr(EnvSettings, "model_config",
                        {**EnvSettings.model_config, "env_file": "/nonexistent.env"})

    with caplog.at_level(logging.WARNING,
                         logger="meta.CodeReviewerAgentTest.env_settings"):
        profile = reviewer_profile_from_env("MODEL_NAME")

    assert profile.litellm_id == "fake_provider/unknown-model-9000"
    assert profile.tier == "unknown"
    assert profile.cost_per_1k_input == 0.0
    assert any("Unknown LiteLLM id" in rec.message for rec in caplog.records)


# ── Happy paths ────────────────────────────────────────────────────


def test_anthropic_haiku_profile(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "anthropic/claude-3-haiku-20240307")
    monkeypatch.setattr(EnvSettings, "model_config",
                        {**EnvSettings.model_config, "env_file": "/nonexistent.env"})

    profile = reviewer_profile_from_env("MODEL_NAME")
    assert profile.litellm_id == "anthropic/claude-3-haiku-20240307"
    assert profile.name == "claude-3-haiku"
    assert profile.tier == "fast"
    assert profile.context_window == 200_000
    assert profile.cost_per_1k_input == pytest.approx(0.00025)
    assert profile.cost_per_1k_output == pytest.approx(0.00125)


def test_alternate_env_var_picks_judge_model(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "anthropic/claude-3-haiku-20240307")
    monkeypatch.setenv("MODEL_NAME_JUDGE", "openai/gpt-4.1-nano")
    monkeypatch.setattr(EnvSettings, "model_config",
                        {**EnvSettings.model_config, "env_file": "/nonexistent.env"})

    judge = reviewer_profile_from_env("MODEL_NAME_JUDGE")
    assert judge.litellm_id == "openai/gpt-4.1-nano"
    assert judge.tier == "fast"
