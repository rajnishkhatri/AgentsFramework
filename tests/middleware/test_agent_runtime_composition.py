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
