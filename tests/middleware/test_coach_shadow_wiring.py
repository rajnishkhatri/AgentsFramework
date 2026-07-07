"""1B-10 — middleware coach shadow wiring (ADR-0007 / ADR-0012).

``/run/stream`` must select the governed coach graph when the request body
carries ``agent_id == "subject-coach-english"`` — in BOTH entry points
(``middleware/app_prod.py`` and the dev runner ``middleware/__main__.py``).
Without this, a coach request is silently served by the DEFAULT graph
(full tool registry, no English guardrail, ``target="call_llm"``) and
Phase-1 shadow traces never accumulate (§12.1 Stage-0).

Layer: L2 (contract-driven; infra mocks only — the AgentFacts registry is
the REAL in-memory implementation per TAP-2, so registration/verification
is genuine, not a mock echo).

Failure paths first (TAP-4):
  * a coach request when no coach runtime is wired → 503, NEVER a fallback
    to the default graph (the default graph is the ungated agent — serving
    it under the coach's identity is the exact leak the contract forbids);
  * absent/foreign ``agent_id`` → default runtime (the least-privilege
    coach graph must never capture plain chat).
"""

from __future__ import annotations

import os
from importlib import reload
from pathlib import Path
from unittest.mock import MagicMock, patch


from services.base_config import AgentConfig, ModelProfile
from services.governance.subject_coach_identity import (
    SUBJECT_COACH_ACCEPT_CONDITION,
    SUBJECT_COACH_AGENT_ID,
    SUBJECT_COACH_CAPABILITIES,
)
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability


_AUTH = {"Authorization": "Bearer test-token"}


def _base_agent_config() -> AgentConfig:
    """A deployment-shaped base config whose identity fields are all the
    DEFAULT agent's (the values the coach contract must override)."""
    return AgentConfig(
        agent_name="governance-agent",
        default_model="test-model-fast",
        models=[
            ModelProfile(
                name="test-model-fast",
                litellm_id="openai/test-model-fast",
                tier="fast",
                context_window=128000,
                cost_per_1k_input=0.1,
                cost_per_1k_output=0.2,
            )
        ],
        max_steps=7,
        capability_gating_enabled=False,
        input_guardrail_accept_condition="",
        eval_capture_target="",
        additional_instructions="",
    )


def _components_bag(agent_config: AgentConfig, registry=None):
    from middleware.composition import AgentComponents

    return AgentComponents(
        agent_config=agent_config,
        tool_registry=MagicMock(name="tool_registry"),
        agent_facts_registry=registry or MagicMock(name="registry"),
        cache_dir=Path("/tmp/agent-coach-wiring-test"),
        goal_judge_config_reader=MagicMock(name="reader"),
        settings=MagicMock(name="settings"),
        memory_service=MagicMock(name="memory_service"),
        memory_autocapture=MagicMock(name="memory_autocapture"),
    )


def _real_registry(tmp_path: Path):
    from services.governance.agent_facts_registry import AgentFactsRegistry

    return AgentFactsRegistry(
        storage_dir=tmp_path / "agent_facts", secret="test-secret"
    )


# ─────────────────────────────────────────────────────────────────────
# build_runtime_graph — bound_capabilities passthrough
# ─────────────────────────────────────────────────────────────────────


class TestBuildRuntimeGraphCapabilityPassthrough:
    """The single build_graph call site must be able to carry the coach's
    declared capability list into the graph (FR-3..6 need it at bind time)."""

    def test_default_is_none_byte_identical(self) -> None:
        from middleware.composition import build_runtime_graph

        spy = MagicMock(name="build_graph")
        build_runtime_graph(_components_bag(_base_agent_config()), spy)
        assert spy.call_args.kwargs["bound_capabilities"] is None

    def test_bound_capabilities_forwarded_to_build_graph(self) -> None:
        from middleware.composition import build_runtime_graph

        spy = MagicMock(name="build_graph")
        build_runtime_graph(
            _components_bag(_base_agent_config()),
            spy,
            bound_capabilities=SUBJECT_COACH_CAPABILITIES,
        )
        assert spy.call_args.kwargs["bound_capabilities"] == SUBJECT_COACH_CAPABILITIES


class TestCoachLeakageCertAttestation:
    """Step 0 (ADR-0020 / Recipe 9): the composition root forwards the coach
    leakage-gate cert attestation into ``build_graph`` as ``coach_goldset_certified``.

    Without it, ``arm()`` pins the gate ``off`` in prod regardless of the config
    mode — the gate can never reach shadow/enforce. The attestation is an explicit
    operator act (``COACH_LEAKAGE_CERT_ATTESTED``, default off): it asserts the
    deployed judge is the ADR-0019-certified ``glm-5.2-fireworks``. Fail-safe: an
    un-attested (or default) deployment forwards ``False`` so ``arm`` stays ``off``.
    """

    def _bag_with_attestation(self, attested: bool):
        bag = _components_bag(_base_agent_config())
        # settings is a MagicMock (truthy by default) — pin the exact flag so the
        # test asserts the wire reads THIS field, not incidental MagicMock truthiness.
        bag.settings.coach_leakage_cert_attested = attested
        return bag

    def test_unattested_forwards_certified_false_fail_safe(self) -> None:
        # FAILURE PATH FIRST: a deployment that has NOT attested the certified judge
        # must forward coach_goldset_certified=False — arm() then pins the gate off.
        from middleware.composition import build_runtime_graph

        spy = MagicMock(name="build_graph")
        build_runtime_graph(self._bag_with_attestation(False), spy)
        assert spy.call_args.kwargs["coach_goldset_certified"] is False

    def test_attested_forwards_certified_true(self) -> None:
        from middleware.composition import build_runtime_graph

        spy = MagicMock(name="build_graph")
        build_runtime_graph(self._bag_with_attestation(True), spy)
        assert spy.call_args.kwargs["coach_goldset_certified"] is True

    def test_settings_default_is_unattested(self) -> None:
        # The real settings default must be off (never arm a gate by default).
        from middleware.composition import AgentRuntimeSettings

        settings = AgentRuntimeSettings()
        assert settings.coach_leakage_cert_attested is False


# ─────────────────────────────────────────────────────────────────────
# build_coach_components — the coach AgentConfig derivation
# ─────────────────────────────────────────────────────────────────────


class TestBuildCoachComponents:
    """Deriving the coach bag from the deployment bag: identity fields come
    from the ratified contract, runtime posture carries from the base."""

    def test_identity_contract_fields_cannot_be_inherited_from_base(self) -> None:
        """Failure path: a base config with gating OFF / default capture tag /
        no guardrail must NOT leak those into the coach instance."""
        from middleware.composition import build_coach_components

        coach = build_coach_components(
            _components_bag(_base_agent_config())
        ).agent_config
        assert coach.agent_name == SUBJECT_COACH_AGENT_ID
        assert coach.capability_gating_enabled is True
        assert coach.input_guardrail_accept_condition == (
            SUBJECT_COACH_ACCEPT_CONDITION
        )
        assert coach.eval_capture_target == "subject_coach"

    def test_persona_rendered_from_template_not_hardcoded(self) -> None:
        """H1: the persona rides additional_instructions and is the rendered
        subject_coach_system_prompt.j2 (mode block present for both modes)."""
        from middleware.composition import build_coach_components

        coach = build_coach_components(
            _components_bag(_base_agent_config())
        ).agent_config
        rendered = coach.additional_instructions.lower()
        assert "pre-submit" in rendered
        assert "post-feedback" in rendered

    def test_runtime_posture_is_carried_from_base(self) -> None:
        """The coach shadows the deployment's models/limits — not AgentConfig
        defaults (an empty models list would break LLMService in prod)."""
        from middleware.composition import build_coach_components

        base = _base_agent_config()
        coach = build_coach_components(_components_bag(base)).agent_config
        assert coach.default_model == "test-model-fast"
        assert coach.models == base.models
        assert coach.max_steps == 7

    def test_only_agent_config_is_replaced_in_the_bag(self) -> None:
        from middleware.composition import build_coach_components

        bag = _components_bag(_base_agent_config())
        coach_bag = build_coach_components(bag)
        assert coach_bag.tool_registry is bag.tool_registry
        assert coach_bag.agent_facts_registry is bag.agent_facts_registry
        assert coach_bag.memory_autocapture is bag.memory_autocapture
        assert coach_bag.agent_config is not bag.agent_config


# ─────────────────────────────────────────────────────────────────────
# app_prod /run/stream — coach selection (request path; no lifespan)
# ─────────────────────────────────────────────────────────────────────


def _empty_async_gen():
    async def _run(*_args, **_kwargs):
        return
        yield  # pragma: no cover — makes this an async generator

    return _run


def _capturing_runtime(captured: dict):
    async def _run(*args, **kwargs):
        captured.update(kwargs)
        return
        yield  # pragma: no cover

    runtime = MagicMock(name="runtime")
    runtime.run = _run
    return runtime


def _build_prod_coach_client(tmp_path: Path):
    """Combined-app TestClient with a REAL in-memory AgentFacts registry and
    two spy runtimes installed on app.state (lifespan not entered — mirrors
    the existing telemetry-harness pattern)."""
    subject = "user_01COACHSUBJECT"
    claims = MagicMock(subject=subject)
    mock_jwt = MagicMock()
    mock_jwt.verify.return_value = claims

    mock_adapters = MagicMock()
    mock_adapters.profile = "v3"
    mock_adapters.jwt_verifier = mock_jwt
    mock_adapters.black_box_relay = None

    registry = _real_registry(tmp_path)

    env = {
        "GCP_EXECUTION_ENV": "cloudrun",
        "ARCHITECTURE_PROFILE": "v3",
        "GCS_FACTS_BUCKET": "test-facts",
        "GCS_TRACES_BUCKET": "test-traces",
        "AGENT_FACTS_SECRET": "test-secret",
        "WORKOS_CLIENT_ID": "client_test",
        "WORKOS_API_KEY": "sk_test",
        "LANGFUSE_PUBLIC_KEY": "pk_test",
        "LANGFUSE_SECRET_KEY": "sk_test",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
    }

    build_components_return = (
        MagicMock(),  # agent_config
        MagicMock(),  # tool_registry
        registry,
        tmp_path / "cache",
        MagicMock(),  # goal_judge_config_reader
    )

    with (
        patch.dict(os.environ, env, clear=False),
        patch("middleware.app_prod.GcsTraceSink", return_value=MagicMock()),
        patch(
            "middleware.app_prod._load_graph_factory",
            return_value=MagicMock(),
        ),
        patch(
            "middleware.composition.build_adapters",
            return_value=mock_adapters,
        ),
    ):
        import middleware.app_prod as mod

        reload(mod)
        with patch.object(
            mod, "_build_components", return_value=build_components_return
        ):
            app = mod.build_combined_app()

    default_captured: dict = {}
    coach_captured: dict = {}
    app.state.runtime = _capturing_runtime(default_captured)
    app.state.coach_runtime = _capturing_runtime(coach_captured)

    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    return client, app, default_captured, coach_captured, registry, subject


class TestProdRunStreamCoachSelection:
    """app_prod /run/stream honors body agent_id (fail-closed first)."""

    def test_coach_request_with_no_coach_runtime_is_503_not_default(
        self, tmp_path: Path
    ) -> None:
        """FAILURE PATH FIRST: an unwired coach runtime must 503 — never
        silently serve the coach request on the ungated default graph."""
        client, app, default_captured, _, _, _ = _build_prod_coach_client(tmp_path)
        app.state.coach_runtime = None
        r = client.post(
            "/run/stream",
            json={"agent_id": SUBJECT_COACH_AGENT_ID, "input": {}},
            headers=_AUTH,
        )
        assert r.status_code == 503
        assert default_captured == {}, (
            "coach request leaked onto the DEFAULT graph — the exact "
            "fallback the least-privilege contract forbids"
        )

    def test_plain_chat_never_uses_coach_runtime(self, tmp_path: Path) -> None:
        client, _, default_captured, coach_captured, _, _ = _build_prod_coach_client(
            tmp_path
        )
        r = client.post("/run/stream", json={"input": {}}, headers=_AUTH)
        assert r.status_code == 200
        assert coach_captured == {}
        assert "identity" in default_captured

    def test_foreign_agent_id_uses_default_runtime(self, tmp_path: Path) -> None:
        client, _, default_captured, coach_captured, _, _ = _build_prod_coach_client(
            tmp_path
        )
        r = client.post(
            "/run/stream",
            json={"agent_id": "some-other-agent", "input": {}},
            headers=_AUTH,
        )
        assert r.status_code == 200
        assert coach_captured == {}
        assert "identity" in default_captured

    def test_coach_agent_id_selects_coach_runtime(self, tmp_path: Path) -> None:
        client, _, default_captured, coach_captured, _, _ = _build_prod_coach_client(
            tmp_path
        )
        r = client.post(
            "/run/stream",
            json={"agent_id": SUBJECT_COACH_AGENT_ID, "input": {}},
            headers=_AUTH,
        )
        assert r.status_code == 200
        assert "identity" in coach_captured
        assert default_captured == {}

    def test_coach_run_identity_is_registered_card_with_subject_owner(
        self, tmp_path: Path
    ) -> None:
        """The run identity is the REGISTERED coach card (guard_input verifies
        it by agent_id, FR-2) with owner = the verified WorkOS subject (H5:
        per-learner eval capture scoping)."""
        client, _, _, coach_captured, registry, subject = _build_prod_coach_client(
            tmp_path
        )
        r = client.post(
            "/run/stream",
            json={"agent_id": SUBJECT_COACH_AGENT_ID, "input": {}},
            headers=_AUTH,
        )
        assert r.status_code == 200
        identity = coach_captured["identity"]
        assert identity.agent_id == SUBJECT_COACH_AGENT_ID
        assert identity.owner == subject
        # The card was registered for real — verification must pass (FR-1/2).
        assert registry.verify(SUBJECT_COACH_AGENT_ID) is True


# ─────────────────────────────────────────────────────────────────────
# app_prod lifespan — coach graph built next to the default graph
# ─────────────────────────────────────────────────────────────────────


def _boot_prod_app_through_lifespan(tmp_path: Path, *, break_coach: bool = False):
    """Enter the prod lifespan (relay-harness pattern) and return
    ``(app, build_graph_spy)`` after shutdown."""
    from unittest.mock import AsyncMock

    mock_adapters = MagicMock()
    mock_adapters.profile = "v3"
    mock_adapters.black_box_relay = None
    mock_adapters.telemetry_exporter = MagicMock()

    mock_pg = MagicMock()
    mock_pg.saver = MagicMock()
    mock_pg_cm = AsyncMock()
    mock_pg_cm.__aenter__.return_value = mock_pg
    mock_pg_cm.__aexit__.return_value = None

    build_components_return = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
        tmp_path / "cache",
        MagicMock(),
    )

    build_graph_spy = MagicMock(name="build_graph")

    env = {
        "GCP_EXECUTION_ENV": "cloudrun",
        "ARCHITECTURE_PROFILE": "v3",
        "GCS_FACTS_BUCKET": "test-facts",
        "GCS_TRACES_BUCKET": "test-traces",
        "AGENT_FACTS_SECRET": "test-secret",
        "WORKOS_CLIENT_ID": "client_test",
        "WORKOS_API_KEY": "sk_test",
        "LANGFUSE_PUBLIC_KEY": "pk_test",
        "LANGFUSE_SECRET_KEY": "sk_test",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
    }

    with (
        patch.dict(os.environ, env, clear=False),
        patch(
            "middleware.composition.build_adapters",
            return_value=mock_adapters,
        ),
        patch(
            "agent_ui_adapter.adapters.runtime.postgres_saver."
            "PostgresCheckpointer.from_env",
            return_value=mock_pg_cm,
        ),
    ):
        import middleware.app_prod as mod

        reload(mod)
        coach_patch = (
            patch.object(
                mod,
                "build_coach_components",
                side_effect=RuntimeError("simulated coach composition failure"),
            )
            if break_coach
            else patch.object(
                mod,
                "build_coach_components",
                wraps=None,
                side_effect=lambda components: _components_bag(_base_agent_config()),
            )
        )
        with (
            patch.object(mod, "GcsTraceSink", return_value=MagicMock()),
            patch.object(mod, "_load_graph_factory", return_value=build_graph_spy),
            patch.object(mod, "LangGraphRuntime", return_value=MagicMock()),
            patch.object(
                mod, "_build_components", return_value=build_components_return
            ),
            coach_patch,
        ):
            app = mod.build_combined_app()
            from fastapi.testclient import TestClient

            with TestClient(app, raise_server_exceptions=False) as client:
                assert client.get("/healthz").status_code == 200
                coach_runtime_during_lifespan = getattr(
                    app.state, "coach_runtime", "MISSING"
                )

    return app, build_graph_spy, coach_runtime_during_lifespan


class TestProdLifespanBuildsCoachGraph:
    def test_coach_build_failure_degrades_never_blocks_boot(
        self, tmp_path: Path
    ) -> None:
        """FAILURE PATH FIRST: a coach composition defect must not take the
        chat backend down — boot succeeds, coach runtime stays None (and the
        request path 503s, asserted above)."""
        _, _, coach_runtime = _boot_prod_app_through_lifespan(
            tmp_path, break_coach=True
        )
        assert coach_runtime is None

    def test_lifespan_builds_coach_graph_with_declared_capabilities(
        self, tmp_path: Path
    ) -> None:
        _, build_graph_spy, coach_runtime = _boot_prod_app_through_lifespan(tmp_path)
        assert coach_runtime not in (None, "MISSING")
        coach_calls = [
            c
            for c in build_graph_spy.call_args_list
            if c.kwargs.get("bound_capabilities") == SUBJECT_COACH_CAPABILITIES
        ]
        assert len(coach_calls) == 1, (
            "lifespan must compile exactly one coach graph bound to the "
            f"declared capabilities; got {build_graph_spy.call_args_list}"
        )


# ─────────────────────────────────────────────────────────────────────
# dev runner (__main__.py) — same wiring, permissive auth
# ─────────────────────────────────────────────────────────────────────


def _boot_dev_app(tmp_path: Path):
    """Boot ``build_dev_app`` through its lifespan with a REAL in-memory
    registry (dev-agent pre-registered) and a build_runtime_graph spy.

    Returns ``(app, TestClient-context, graph_calls)`` — the caller drives
    requests inside the returned context manager.
    """
    from contextlib import contextmanager

    from middleware.composition import AgentComponents

    registry = _real_registry(tmp_path)
    registry.register(
        AgentFacts(
            agent_id="dev-agent",
            agent_name="Dev Agent",
            owner="dev-user",
            version="1.0.0",
            description="Local development agent",
            capabilities=[Capability(name="delegate.subagent.*")],
            status=IdentityStatus.ACTIVE,
        ),
        registered_by="test-bootstrap",
    )

    full_bag = AgentComponents(
        agent_config=_base_agent_config(),
        tool_registry=MagicMock(),
        agent_facts_registry=registry,
        cache_dir=tmp_path / "cache",
        goal_judge_config_reader=MagicMock(),
        settings=MagicMock(),
        memory_service=MagicMock(),
        memory_autocapture=MagicMock(),
    )

    graph_calls: list[dict] = []

    def _spy_build_runtime_graph(components, build_graph, **kwargs):
        graph_calls.append({"agent_config": components.agent_config, **kwargs})
        return MagicMock(name="graph")

    import middleware.__main__ as mod

    reload(mod)

    @contextmanager
    def _running():
        with (
            patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}, clear=False),
            patch.object(mod, "_GCP_EXECUTION_ENV", None),
            patch.object(mod, "_build_agent_components", return_value=full_bag),
            patch.object(mod, "_load_graph_factory", return_value=MagicMock()),
            patch.object(
                mod, "build_runtime_graph", side_effect=_spy_build_runtime_graph
            ),
            patch.object(mod, "LangGraphRuntime", return_value=MagicMock()),
            patch.object(mod, "TraceService", return_value=MagicMock()),
            patch.object(mod, "JsonlFileTraceSink", return_value=MagicMock()),
        ):
            app = mod.build_dev_app()
            from fastapi.testclient import TestClient

            with TestClient(app, raise_server_exceptions=False) as client:
                yield app, client

    return _running, graph_calls, registry


class TestDevRunnerCoachWiring:
    def test_dev_lifespan_builds_coach_graph_with_declared_capabilities(
        self, tmp_path: Path
    ) -> None:
        running, graph_calls, _ = _boot_dev_app(tmp_path)
        with running():
            pass
        coach_calls = [
            c
            for c in graph_calls
            if c.get("bound_capabilities") == SUBJECT_COACH_CAPABILITIES
        ]
        assert len(coach_calls) == 1, (
            f"dev lifespan must compile one coach graph; got {graph_calls}"
        )
        assert coach_calls[0]["agent_config"].agent_name == SUBJECT_COACH_AGENT_ID

    def test_dev_run_stream_selects_coach_runtime_with_dev_owner(
        self, tmp_path: Path
    ) -> None:
        running, _, registry = _boot_dev_app(tmp_path)
        with running() as (app, client):
            default_captured: dict = {}
            coach_captured: dict = {}
            app.state.runtime = _capturing_runtime(default_captured)
            app.state.coach_runtime = _capturing_runtime(coach_captured)

            # Failure path first: plain chat must not touch the coach graph.
            r = client.post("/run/stream", json={"input": {}}, headers=_AUTH)
            assert r.status_code == 200
            assert coach_captured == {}

            r = client.post(
                "/run/stream",
                json={"agent_id": SUBJECT_COACH_AGENT_ID, "input": {}},
                headers=_AUTH,
            )
            assert r.status_code == 200
            identity = coach_captured["identity"]
            assert identity.agent_id == SUBJECT_COACH_AGENT_ID
            assert identity.owner == "dev-user"
            assert registry.verify(SUBJECT_COACH_AGENT_ID) is True

    def test_dev_coach_request_with_no_coach_runtime_is_503(
        self, tmp_path: Path
    ) -> None:
        running, _, _ = _boot_dev_app(tmp_path)
        with running() as (app, client):
            default_captured: dict = {}
            app.state.runtime = _capturing_runtime(default_captured)
            app.state.coach_runtime = None
            r = client.post(
                "/run/stream",
                json={"agent_id": SUBJECT_COACH_AGENT_ID, "input": {}},
                headers=_AUTH,
            )
            assert r.status_code == 503
            assert default_captured == {}
