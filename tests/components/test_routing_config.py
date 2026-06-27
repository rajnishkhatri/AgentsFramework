"""L1 Deterministic: Tests for components/routing_config.py.

Pure TDD (Red-Green-Refactor). Tests defaults, validation, roundtrip.
"""

from __future__ import annotations


from components.routing_config import RoutingConfig


class TestRoutingConfig:
    def test_defaults(self):
        cfg = RoutingConfig()
        assert cfg.default_model == "gpt-4o-mini"
        assert cfg.escalate_after_failures == 2
        assert cfg.max_escalations == 3
        assert cfg.budget_downgrade_threshold == 0.8

    def test_override_defaults(self):
        cfg = RoutingConfig(
            default_model="gpt-4o",
            escalate_after_failures=3,
            max_escalations=5,
            budget_downgrade_threshold=0.9,
        )
        assert cfg.default_model == "gpt-4o"
        assert cfg.escalate_after_failures == 3

    def test_roundtrip_json(self):
        cfg = RoutingConfig(default_model="claude-3-sonnet", max_escalations=10)
        restored = RoutingConfig.model_validate_json(cfg.model_dump_json())
        assert restored == cfg


class TestDefaultModelTracksActiveSet:
    """F1/F10: a bare RoutingConfig() must resolve the ACTIVE set's default, not
    always the openai default. The field and AgentConfig.models must come from
    the SAME registry read so they can never disagree."""

    def test_bare_default_is_openai_when_unset(self, monkeypatch):
        monkeypatch.delenv("MODEL_PROFILE_SET", raising=False)
        assert RoutingConfig().default_model == "gpt-4o-mini"

    def test_bare_default_tracks_anthropic_set(self, monkeypatch):
        monkeypatch.setenv("MODEL_PROFILE_SET", "anthropic")
        assert RoutingConfig().default_model == "claude-haiku-4-5"

    def test_bare_default_tracks_deepseek_set(self, monkeypatch):
        monkeypatch.setenv("MODEL_PROFILE_SET", "deepseek")
        assert RoutingConfig().default_model == "deepseek-v4-flash"

    def test_explicit_default_overrides_env(self, monkeypatch):
        # An explicitly-passed default_model (the primary builder path) wins over
        # the env-derived factory — callers that have the registry's default in
        # hand pass it directly.
        monkeypatch.setenv("MODEL_PROFILE_SET", "anthropic")
        assert (
            RoutingConfig(default_model="explicit-name").default_model
            == "explicit-name"
        )

    def test_routing_and_agent_default_agree_under_set(self, monkeypatch):
        # The load-bearing invariant: under a non-openai set, the routing default
        # equals the registry default (so it's a model that EXISTS in the set).
        from services.llm_config import build_model_registry

        monkeypatch.setenv("MODEL_PROFILE_SET", "anthropic")
        models, agent_default = build_model_registry("anthropic")
        routing_default = RoutingConfig().default_model
        assert routing_default == agent_default
        assert routing_default in {m.name for m in models}
