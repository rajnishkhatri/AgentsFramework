"""L2 contract tests for agent runtime composition (local vs prod profiles)."""

from __future__ import annotations

from pathlib import Path

import pytest

from middleware.composition import AgentRuntimeSettings, build_components


AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestBuildComponentsLocal:
    def test_local_selects_file_registry_and_reader(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings(
            agent_env="local",
            goal_judge_enabled=True,
            goal_judge_downgrade_enabled=False,
        )
        components = build_components(settings, agent_root=tmp_path)
        assert components.agent_config.goal_judge_enabled is True
        assert components.cache_dir == tmp_path / "cache"
        from services.governance.agent_facts_registry import AgentFactsRegistry

        assert isinstance(components.agent_facts_registry, AgentFactsRegistry)
        resolved = components.goal_judge_config_reader.get()
        assert resolved.source in ("env", "default")

    def test_file_io_is_not_cacheable(self, tmp_path, monkeypatch):
        """Regression (2026-06-12 live stress run): cached file_io reads served
        stale content after the same path was overwritten in-thread."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings(agent_env="local")
        components = build_components(settings, agent_root=tmp_path)
        assert components.tool_registry.is_cacheable("file_io") is False

    def test_shell_is_not_cacheable(self, tmp_path, monkeypatch):
        """Same hazard as file_io: every allowlisted shell command reads mutable
        filesystem state, and the thread-level tool_cache never invalidates."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings(agent_env="local")
        components = build_components(settings, agent_root=tmp_path)
        assert components.tool_registry.is_cacheable("shell") is False


class TestBuildComponentsProd:
    def test_prod_requires_gcs_facts_bucket(self, tmp_path):
        settings = AgentRuntimeSettings(agent_env="prod", gcs_facts_bucket="")
        with pytest.raises(RuntimeError, match="GCS_FACTS_BUCKET"):
            build_components(settings, agent_root=tmp_path)

    def test_prod_selects_gcs_registry_and_default_config_uri(self, tmp_path):
        settings = AgentRuntimeSettings(
            agent_env="prod",
            gcs_facts_bucket="my-facts-bucket",
        )
        components = build_components(settings, agent_root=tmp_path)
        from services.governance.agent_facts_gcs_registry import AgentFactsGcsRegistry

        assert isinstance(components.agent_facts_registry, AgentFactsGcsRegistry)
        assert components.goal_judge_config_reader._uri == (
            "gs://my-facts-bucket/ops/goal_judge_config.json"
        )


class TestTieredLoopFlags:
    """Step 0a (e2e-stress plan §2.1): the loop flags must reach AgentConfig
    from env, and must default OFF so prod parity with the shadow-first
    defaults in services/base_config.py is preserved.

    Failure-first (AP6): the headline guard is the OFF default — a stray prod
    flip is the dangerous regression, not a missed env read. No live LLM (AP5):
    this only inspects the built config.
    """

    def test_defaults_are_off_prod_parity(self, tmp_path, monkeypatch):
        """No env vars set -> loops dark, matching the live deployment."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings(agent_env="local")
        components = build_components(settings, agent_root=tmp_path)
        cfg = components.agent_config
        assert cfg.reflexion_enabled is False
        assert cfg.plan_source == "deterministic"
        assert cfg.max_reflexion_attempts == 2
        # T3 (Phase 4): the fan-out fork AND the fault-injection hook are OFF by
        # default — prod parity. fanout_fault_inject leaking to prod is a named
        # §5 risk; this is the guard that fails if a default flips.
        assert cfg.t3_fanout_enabled is False
        assert cfg.fanout_fault_inject is False
        # Carrier-gate enforcement (Phase 2): OFF by default → "off" mode (shadow
        # only). A stray flip to raise/degrade in prod is the dangerous regression.
        assert cfg.carrier_gate_enforce_mode == "off"

    def test_env_flips_propagate_into_agent_config(self, tmp_path, monkeypatch):
        """The stress revision's env reaches the live AgentConfig (§2.1)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {
                "AGENT_ENV": "local",
                "REFLEXION_ENABLED": "1",
                "PLANNING_PLAN_SOURCE": "generated",
                "MAX_REFLEXION_ATTEMPTS": "3",
            }
        )
        components = build_components(settings, agent_root=tmp_path)
        cfg = components.agent_config
        assert cfg.reflexion_enabled is True
        assert cfg.plan_source == "generated"
        assert cfg.max_reflexion_attempts == 3

    def test_t3_env_flips_propagate_into_agent_config(self, tmp_path, monkeypatch):
        """The stress revision's T3 env reaches the live AgentConfig."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {
                "AGENT_ENV": "local",
                "T3_FANOUT_ENABLED": "1",
                "FANOUT_FAULT_INJECT": "1",
            }
        )
        components = build_components(settings, agent_root=tmp_path)
        cfg = components.agent_config
        assert cfg.t3_fanout_enabled is True
        assert cfg.fanout_fault_inject is True

    def test_carrier_gate_enforce_flag_off_is_mode_off(self, tmp_path, monkeypatch):
        """Phase 2: flag OFF → "off" mode regardless of env (prod parity)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        for env in ("local", "prod"):
            settings = AgentRuntimeSettings(agent_env=env, gcs_facts_bucket="b")
            cfg = build_components(settings, agent_root=tmp_path).agent_config
            assert cfg.carrier_gate_enforce_mode == "off"

    def test_carrier_gate_enforce_dev_raises(self, tmp_path, monkeypatch):
        """Flag ON in a local/dev env → "raise" (fail loud at the source)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {"AGENT_ENV": "local", "CARRIER_GATE_ENFORCE_ENABLED": "1"}
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.carrier_gate_enforce_mode == "raise"

    def test_carrier_gate_enforce_prod_degrades(self, tmp_path, monkeypatch):
        """Flag ON in prod → "degrade" (loud trace, run continues — never block)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {
                "AGENT_ENV": "prod",
                "GCS_FACTS_BUCKET": "b",
                "CARRIER_GATE_ENFORCE_ENABLED": "1",
            }
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.carrier_gate_enforce_mode == "degrade"

    def test_from_mapping_parses_bool_and_int(self):
        """REFLEXION_ENABLED coerces like the other flags; the attempt count
        is an int, not the raw string."""
        s = AgentRuntimeSettings.from_mapping(
            {"AGENT_ENV": "local", "REFLEXION_ENABLED": "true", "MAX_REFLEXION_ATTEMPTS": "5"}
        )
        assert s.reflexion_enabled is True
        assert s.max_reflexion_attempts == 5
        assert isinstance(s.max_reflexion_attempts, int)

    def test_invalid_plan_source_is_rejected_at_startup(self):
        """An out-of-range PLANNING_PLAN_SOURCE must fail loudly (Literal guard),
        not silently fall back to deterministic."""
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            AgentRuntimeSettings.from_mapping(
                {"AGENT_ENV": "local", "PLANNING_PLAN_SOURCE": "bogus"}
            )
