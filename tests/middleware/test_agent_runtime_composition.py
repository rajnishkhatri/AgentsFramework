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


class TestModelProfileSetWiring:
    """MODEL_PROFILE_SET selects which H2 registry the composition root wires.

    Rejection / fail-loud paths first (TAP-4): the dangerous case is the
    Anthropic Auto stack wired without its key (every Auto turn would silently
    401), and the second is a flagged-on Auto stack that is NOT byte-identical
    when the flag is off.
    """

    def _local(self, tmp_path, monkeypatch, **kw):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        return AgentRuntimeSettings(agent_env="local", **kw)

    # ── Fail-loud: anthropic set without the key ──────────────────────────
    def test_anthropic_set_without_key_fails_loud(self, tmp_path, monkeypatch):
        from middleware.composition import MissingEnvError

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        settings = self._local(
            tmp_path, monkeypatch, model_profile_set="anthropic", anthropic_api_key=""
        )
        with pytest.raises(MissingEnvError):
            build_components(settings, agent_root=tmp_path)

    def test_openai_set_does_not_require_anthropic_key(self, tmp_path, monkeypatch):
        """The default set has no anthropic/* model, so the key guard must not
        fire — a stray guard would break every existing OpenAI deploy."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        settings = self._local(tmp_path, monkeypatch, anthropic_api_key="")
        components = build_components(settings, agent_root=tmp_path)  # no raise
        assert components.agent_config.models  # populated

    # ── Flag OFF is byte-identical to today (OpenAI stack) ────────────────
    def test_default_set_is_openai_byte_identical(self, tmp_path, monkeypatch):
        settings = self._local(tmp_path, monkeypatch)  # default model_profile_set
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.default_model == "gpt-4o-mini"
        fast = next(m for m in cfg.models if m.tier == "fast")
        capable = next(m for m in cfg.models if m.tier == "capable")
        assert fast.name == "gpt-4o-mini"
        assert capable.name == "gpt-4o"
        assert fast.name.startswith("gpt-")

    # ── Flag ON is the 3-tier all-Anthropic stack ─────────────────────────
    def test_anthropic_set_three_tier_order(self, tmp_path, monkeypatch):
        settings = self._local(
            tmp_path,
            monkeypatch,
            model_profile_set="anthropic",
            anthropic_api_key="sk-ant-test",
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.default_model == "claude-haiku-4-5"
        first = {"fast": None, "capable": None, "reasoning": None}
        for m in cfg.models:
            if m.tier in first and first[m.tier] is None:
                first[m.tier] = m.name
        assert first["fast"] == "claude-haiku-4-5"
        assert first["capable"] == "claude-sonnet-4-6"
        assert first["reasoning"] == "claude-opus-4-8"
        # no gpt-* wins a first-match under the anthropic set
        for tier in ("fast", "capable", "reasoning"):
            assert not first[tier].startswith("gpt-")

    # ── Fail-loud: deepseek set without the key (generalized guard) ────────
    def test_deepseek_set_without_key_fails_loud(self, tmp_path, monkeypatch):
        from middleware.composition import MissingEnvError

        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        settings = self._local(
            tmp_path, monkeypatch, model_profile_set="deepseek", deepseek_api_key=""
        )
        with pytest.raises(MissingEnvError):
            build_components(settings, agent_root=tmp_path)

    def test_openai_set_does_not_require_deepseek_key(self, tmp_path, monkeypatch):
        """The generalized provider→key guard must still let the keyless openai
        default set boot — a stray deepseek guard would break every existing
        deploy just like a stray anthropic one would."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        settings = self._local(tmp_path, monkeypatch, deepseek_api_key="")
        components = build_components(settings, agent_root=tmp_path)  # no raise
        assert components.agent_config.models

    # ── Flag ON is the DeepSeek V4 stack (Flash fast+capable / Pro reasoning) ──
    def test_deepseek_set_three_tier_order(self, tmp_path, monkeypatch):
        settings = self._local(
            tmp_path,
            monkeypatch,
            model_profile_set="deepseek",
            deepseek_api_key="sk-deepseek-test",
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.default_model == "deepseek-v4-flash"
        first = {"fast": None, "capable": None, "reasoning": None}
        for m in cfg.models:
            if m.tier in first and first[m.tier] is None:
                first[m.tier] = m.name
        assert first["fast"] == "deepseek-v4-flash"
        assert first["capable"] == "deepseek-v4-flash-capable"
        assert first["reasoning"] == "deepseek-v4-pro"
        for tier in ("fast", "capable", "reasoning"):
            assert not first[tier].startswith("gpt-")


class TestMemoryBackendSelection:
    """Live-infra Piece B: MEM0_API_KEY selects the durable Mem0 backend.

    The backend only constructs the SDK client lazily (on first call), so this
    asserts the SELECTION without any live Mem0 round-trip — failure path first.
    """

    def _service_backend(self, settings, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        components = build_components(settings, agent_root=tmp_path)
        # LongTermMemoryService holds its backend privately; reach it for the
        # selection assertion (this is a wiring contract test).
        return components.memory_service._backend

    def test_no_key_selects_in_memory_backend(self, tmp_path, monkeypatch):
        from services.long_term_memory import InMemoryMemoryBackend

        settings = AgentRuntimeSettings(agent_env="local", mem0_api_key="")
        backend = self._service_backend(settings, tmp_path, monkeypatch)
        assert isinstance(backend, InMemoryMemoryBackend)

    def test_key_present_selects_mem0_backend(self, tmp_path, monkeypatch):
        """Legacy assertion (pre-Phase-4): with ``MEMORY_BACKEND`` unset (default
        ``"inmemory"``), the historical ``mem0_api_key`` selector no longer wins —
        Phase 4 retired it. The mem0 backend file stays on disk (Phase 5 S6
        deletes it after the 24h soak) so the import still works, but the
        composition root never wires it: keys live in env solely for the
        24h-rollback window (rollback redeploys the prior revision).
        """
        from services.long_term_memory import InMemoryMemoryBackend

        settings = AgentRuntimeSettings(
            agent_env="local", mem0_api_key="mem0_test_key"
        )
        backend = self._service_backend(settings, tmp_path, monkeypatch)
        assert isinstance(backend, InMemoryMemoryBackend)


# ─────────────────────────────────────────────────────────────────────
# Phase 4 (replace-mem0-pgvector) — MEMORY_BACKEND selector
#
# The plan's Gate (Phase 4 → Phase 5) calls out the rejection test FIRST:
# ``MEMORY_BACKEND=pgvector`` with no ``DATABASE_URL`` MUST raise at
# composition time, NOT silently fall back to ``InMemoryMemoryBackend``
# (composition-root scope guard). Failure-paths-first per AGENTS.md.
# ─────────────────────────────────────────────────────────────────────


class TestPgvectorBackendSelectionRejectionPaths:
    """Phase 4: rejection paths come FIRST (failure-paths-first per AGENTS.md).

    Two ways to misconfigure the pgvector selector — both MUST fail at
    composition time rather than silently degrade to InMemory in prod:

      * ``MEMORY_BACKEND=pgvector`` set but no ``DATABASE_URL``.
      * Unknown ``MEMORY_BACKEND`` value (typo guard).
    """

    def test_pgvector_without_database_url_raises(self, tmp_path, monkeypatch):
        from middleware.composition import MissingEnvError

        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings(
            agent_env="local",
            memory_backend="pgvector",
            database_url="",
        )
        with pytest.raises(MissingEnvError) as excinfo:
            build_components(settings, agent_root=tmp_path)
        assert "DATABASE_URL" in str(excinfo.value)

    def test_pgvector_without_embedding_provider_raises(
        self, tmp_path, monkeypatch
    ):
        """OPENAI_API_KEY drives ``_build_embedding_client`` — absent, no
        EmbeddingClient can be constructed and the backend would store rows
        whose embeddings dimension was unverified. Must raise, not warn.
        """
        from middleware.composition import MissingEnvError

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings(
            agent_env="local",
            memory_backend="pgvector",
            database_url="postgresql://stub@localhost/x",
            openai_api_key="",
        )
        with pytest.raises(MissingEnvError) as excinfo:
            build_components(settings, agent_root=tmp_path)
        assert "OPENAI_API_KEY" in str(excinfo.value)

    def test_unknown_memory_backend_value_raises(self, tmp_path, monkeypatch):
        """Pydantic Literal validation rejects the typo at AgentRuntimeSettings
        construction. Whether the error type is ValueError or pydantic's
        ValidationError is not load-bearing — we just want to fail closed.
        """
        with pytest.raises(Exception) as excinfo:
            AgentRuntimeSettings(
                agent_env="local",
                memory_backend="qdrant",  # type: ignore[arg-type]
            )
        assert "memory_backend" in str(excinfo.value).lower() or (
            "qdrant" in str(excinfo.value)
        )


class TestPgvectorBackendSelectionAcceptance:
    """Phase 4 acceptance: happy paths.

    Build only goes as far as the LongTermMemoryService — the pgvector
    backend lazily opens its pool on first call, so the construction
    contract test does not require a live Postgres on this machine.
    """

    def _service_backend(self, settings, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        components = build_components(settings, agent_root=tmp_path)
        return components.memory_service._backend

    def test_default_unset_selects_in_memory(self, tmp_path, monkeypatch):
        """``MEMORY_BACKEND`` defaults to ``"inmemory"`` — dev/test posture
        survives the Phase 4 swap byte-identical.
        """
        from services.long_term_memory import InMemoryMemoryBackend

        settings = AgentRuntimeSettings(agent_env="local")
        backend = self._service_backend(settings, tmp_path, monkeypatch)
        assert isinstance(backend, InMemoryMemoryBackend)

    def test_inmemory_explicit_selects_in_memory(self, tmp_path, monkeypatch):
        from services.long_term_memory import InMemoryMemoryBackend

        settings = AgentRuntimeSettings(
            agent_env="local", memory_backend="inmemory"
        )
        backend = self._service_backend(settings, tmp_path, monkeypatch)
        assert isinstance(backend, InMemoryMemoryBackend)

    def test_pgvector_with_db_and_key_selects_pgvector(
        self, tmp_path, monkeypatch
    ):
        from services.memory_backends.pgvector import PgVectorMemoryBackend

        settings = AgentRuntimeSettings(
            agent_env="local",
            memory_backend="pgvector",
            database_url="postgresql://stub@localhost/x",
            openai_api_key="sk-test-dummy",
        )
        backend = self._service_backend(settings, tmp_path, monkeypatch)
        assert isinstance(backend, PgVectorMemoryBackend)


class TestAutocaptureEnablePolicyGuard:
    """The composition root must gate write-back on the enable-policy guard.

    The ``MEMORY_AUTOCAPTURE_ENABLED`` flag is the operator's intent; write-back
    only actually turns on when a passing frozen-test-split calibration
    certificate is also present. Flag-on-but-no-cert must fail SAFE to shadow —
    these tests pin that the constructed service reflects the guard's decision,
    not the raw flag.
    """

    def _autocapture(self, settings, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        return build_components(settings, agent_root=tmp_path).memory_autocapture

    def test_flag_off_is_shadow(self, tmp_path, monkeypatch):
        settings = AgentRuntimeSettings(
            agent_env="local", memory_autocapture_enabled=False
        )
        svc = self._autocapture(settings, tmp_path, monkeypatch)
        assert svc._write_back is False

    def test_flag_on_but_no_certificate_stays_shadow(self, tmp_path, monkeypatch):
        # The dangerous case: someone sets the env flag but never ran the gate.
        # The guard must keep write-back OFF (never store ungated).
        settings = AgentRuntimeSettings(
            agent_env="local",
            memory_autocapture_enabled=True,
            memory_autocapture_cert="",
        )
        svc = self._autocapture(settings, tmp_path, monkeypatch)
        assert svc._write_back is False

    def test_flag_on_with_passing_test_certificate_enables(
        self, tmp_path, monkeypatch
    ):
        import json

        from services.governance.memory_enable_policy import CERT_SCHEMA

        cert = tmp_path / "cert.json"
        cert.write_text(
            json.dumps(
                {
                    "schema": CERT_SCHEMA,
                    "passed": True,
                    "split": "test",
                    "total_rows": 41,
                    "gates": [
                        {"name": n, "passed": True}
                        for n in (
                            "store_class_precision",
                            "false_store_on_trivia",
                            "mistype_rate",
                            "pii_flip_rate",
                            "kappa_judge_vs_gold",
                        )
                    ],
                }
            ),
            encoding="utf-8",
        )
        settings = AgentRuntimeSettings(
            agent_env="local",
            memory_autocapture_enabled=True,
            memory_autocapture_cert=str(cert),
        )
        svc = self._autocapture(settings, tmp_path, monkeypatch)
        assert svc._write_back is True


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


class TestC1ContextCompactionFlags:
    """C1 Phase 4 (design §9): the 7 context_* fields thread through the
    composition root (env → AgentRuntimeSettings → AgentConfig).

    Failure-first (Protocol A): the headline guard is the OFF default — the
    impl plan's "byte-identical-when-off proof" depends on the master flag
    being False after an empty env, and every numeric default being exactly
    the §9 table value. A drift here silently activates the WRITE seam.
    """

    def test_empty_env_keeps_master_flag_off(self, tmp_path, monkeypatch):
        """Empty env ⇒ context_compact_messages_enabled is False on AgentConfig.
        This is the byte-identical-when-off proof (design §9)."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings(agent_env="local")
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.context_compact_messages_enabled is False
        # The other six knobs also surface their byte-identical defaults so a
        # rev that flips the master flag inherits the §9-tabled values.
        assert cfg.context_compact_trigger_fraction == 0.6
        assert cfg.context_observation_clear_fraction == 0.3
        assert cfg.context_keep_last_k == 10
        assert cfg.context_mask_after_steps == 10
        assert cfg.context_compact_cooldown_steps == 5
        assert cfg.context_constraint_reinject_turns == 0
        # Fix 1 — the user-pin harvest gate is OFF by default, so both fold
        # sites pass user_constraints=[] (byte-identical with the prior code).
        assert cfg.context_extract_user_constraints is False

    def test_extract_user_constraints_env_alias_flips_on(
        self, tmp_path, monkeypatch
    ):
        """Fix 1: CONTEXT_EXTRACT_USER_CONSTRAINTS coerces through the bool-list
        like the master flag, flipping the harvest gate ON."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {"AGENT_ENV": "local", "CONTEXT_EXTRACT_USER_CONSTRAINTS": "1"}
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.context_extract_user_constraints is True

    def test_master_flag_env_alias_is_context_compact_messages(self, tmp_path, monkeypatch):
        """The env alias CONTEXT_COMPACT_MESSAGES coerces through the bool-list
        like REFLEXION_ENABLED / T3_FANOUT_ENABLED."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {"AGENT_ENV": "local", "CONTEXT_COMPACT_MESSAGES": "1"}
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.context_compact_messages_enabled is True

    def test_numeric_aliases_thread_through_coercion_arm(self, tmp_path, monkeypatch):
        """The six numeric knobs flip from raw strings through the coercion
        arm (composition.py:521-522) onto AgentConfig. Mirrors the
        MAX_REFLEXION_ATTEMPTS pattern; int and float both honored."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {
                "AGENT_ENV": "local",
                "CONTEXT_COMPACT_TRIGGER_FRACTION": "0.75",
                "CONTEXT_OBSERVATION_CLEAR_FRACTION": "0.25",
                "CONTEXT_KEEP_LAST_K": "12",
                "CONTEXT_MASK_AFTER_STEPS": "8",
                "CONTEXT_COMPACT_COOLDOWN_STEPS": "3",
                "CONTEXT_CONSTRAINT_REINJECT_TURNS": "4",
            }
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.context_compact_trigger_fraction == 0.75
        assert cfg.context_observation_clear_fraction == 0.25
        assert cfg.context_keep_last_k == 12
        assert cfg.context_mask_after_steps == 8
        assert cfg.context_compact_cooldown_steps == 3
        assert cfg.context_constraint_reinject_turns == 4
        # Types are stable — the coercion arm hands typed values to pydantic,
        # not raw strings (the impl-plan's "direct copy" semantics).
        assert isinstance(cfg.context_compact_trigger_fraction, float)
        assert isinstance(cfg.context_keep_last_k, int)
        assert isinstance(cfg.context_compact_cooldown_steps, int)

    def test_master_flag_env_off_yields_disabled(self, tmp_path, monkeypatch):
        """Explicit OFF must round-trip; mirrors REFLEXION_ENABLED."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        settings = AgentRuntimeSettings.from_mapping(
            {"AGENT_ENV": "local", "CONTEXT_COMPACT_MESSAGES": "false"}
        )
        cfg = build_components(settings, agent_root=tmp_path).agent_config
        assert cfg.context_compact_messages_enabled is False
