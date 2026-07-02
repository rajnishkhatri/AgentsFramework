"""Architecture gate: declared capabilities == bound tools (ADR-0007, FR-3/4/5/6).

This is the hard mechanical enforcement the ADR commits to: the behavior that
would otherwise silently regress — an agent quietly gaining ``shell`` — becomes a
gate that MUST pass (root AGENTS.md: ``tests/architecture/`` is the hard
enforcement). The same template-as-enforcement tactic the repo already uses.

Two properties are locked in:
  * **declared == bound** — the capability-gating seam binds EXACTLY the declared
    tools; ``shell``/``web_search`` present in the registry are NOT bound
    (FR-3/FR-4/FR-6).
  * **fail-fast at build** — a capability naming a tool absent from the registry
    raises at ``build_graph`` (FR-5), observable end-to-end (not just in the unit).

No live LLM: a real ``ToolRegistry`` with stub executors + a real ``AgentConfig``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import BaseModel

from components.capability_gating import (
    CapabilityToolMissingError,
    derive_bound_tools,
    filter_registry_schemas,
)
from orchestration.react_loop import build_graph
from services.base_config import AgentConfig
from services.tools.registry import ToolDefinition, ToolRegistry


class _Noop(BaseModel):
    pass


def _stub(args: dict) -> str:  # pragma: no cover - never executed in these tests
    return "ok"


def _full_registry() -> ToolRegistry:
    """A registry that HAS shell/web_search — the tools a coach must not gain."""
    return ToolRegistry(
        {
            "think": ToolDefinition(executor=_stub, schema=_Noop),
            "file_io": ToolDefinition(executor=_stub, schema=_Noop),
            "shell": ToolDefinition(executor=_stub, schema=_Noop),
            "web_search": ToolDefinition(executor=_stub, schema=_Noop),
        }
    )


class TestDeclaredEqualsBound:
    def test_declared_equals_bound_excludes_shell_and_web_search(self) -> None:
        """FR-3/FR-4/FR-6: binding exactly the declared capabilities drops the
        privileged tools even though the registry provides them."""
        registry = _full_registry()
        gate = derive_bound_tools(
            capability_names=["think", "file_io"],
            available_tool_names=registry.tool_names(),
        )
        # declared == bound
        assert (
            set(gate.bound_tool_names)
            == set(gate.capabilities)
            == {
                "think",
                "file_io",
            }
        )
        # The schemas actually reaching the LLM binding contain no privileged tool.
        bound_schemas = filter_registry_schemas(
            registry.get_schemas(), gate.bound_tool_names
        )
        bound_names = {s["name"] for s in bound_schemas}
        assert bound_names == {"think", "file_io"}
        assert "shell" not in bound_names
        assert "web_search" not in bound_names


class TestFailFastAtBuild:
    def test_missing_tool_capability_fails_fast_at_build(self) -> None:
        """FR-5: a capability naming a tool the registry can't provide stops the
        build — a declared-but-unavailable tool is a config bug, not a no-op."""
        cfg = AgentConfig(capability_gating_enabled=True)
        with pytest.raises(CapabilityToolMissingError):
            build_graph(
                agent_config=cfg,
                tool_registry=_full_registry(),
                bound_capabilities=["think", "python"],  # python is not registered
            )

    def test_flag_off_is_byte_identical(self) -> None:
        """With gating OFF the build ignores bound_capabilities entirely (the full
        registry is bound, as today) — no raise even for a bogus capability."""
        cfg = AgentConfig(capability_gating_enabled=False)
        # Must not raise: gating is off, so the missing-tool check never runs.
        build_graph(
            agent_config=cfg,
            tool_registry=_full_registry(),
            bound_capabilities=["think", "python"],
        )


class TestInjectableAcceptCondition:
    def _captured_accept_condition(self, cfg: AgentConfig) -> str:
        """Build a graph and capture the accept_condition passed to InputGuardrail."""
        captured: dict[str, str] = {}
        real_init = _real_input_guardrail_init()

        def _spy(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            captured["accept_condition"] = kwargs.get("accept_condition", "")
            return real_init(self, *args, **kwargs)

        with patch("orchestration.react_loop.InputGuardrail.__init__", _spy):
            build_graph(agent_config=cfg, tool_registry=_full_registry())
        return captured.get("accept_condition", "")

    def test_injected_condition_reaches_guardrail(self) -> None:
        """FR-7: a domain accept_condition on AgentConfig flows into the guardrail."""
        condition = "The input is about learning or teaching English."
        cfg = AgentConfig(input_guardrail_accept_condition=condition)
        assert self._captured_accept_condition(cfg) == condition

    def test_empty_condition_falls_back_to_default(self) -> None:
        """Unset ⇒ the default prompt-injection condition (byte-identical)."""
        cfg = AgentConfig()
        assert (
            self._captured_accept_condition(cfg)
            == "The input is a legitimate user query"
        )


def _real_input_guardrail_init():
    """The unpatched InputGuardrail.__init__, for the spy to delegate to."""
    from services.guardrails import InputGuardrail

    return InputGuardrail.__init__


def _production_shaped_registry() -> ToolRegistry:
    """Same tool vocabulary as middleware/composition.py's production registry."""
    return ToolRegistry(
        {
            name: ToolDefinition(executor=_stub, schema=_Noop)
            for name in (
                "shell",
                "file_io",
                "state_file",
                "state_todo",
                "task",
                "think",
                "web_search",
            )
        }
    )


class TestSubjectCoachContract:
    """FR-3/4/5/6 for the subject-coach-english instance (agent spec §3.2).

    The coach's declared contract, run against the PRODUCTION tool vocabulary:
    exactly ``think`` + ``file_io`` bound; shell/web_search/task never reach
    the LLM binding; a registry missing a declared tool fails the build.
    """

    def test_coach_binds_exactly_declared_and_never_privileged(self) -> None:
        from services.governance.subject_coach_identity import (
            SUBJECT_COACH_CAPABILITIES,
        )

        registry = _production_shaped_registry()
        gate = derive_bound_tools(
            capability_names=SUBJECT_COACH_CAPABILITIES,
            available_tool_names=registry.tool_names(),
        )
        assert (
            set(gate.bound_tool_names)
            == set(gate.capabilities)
            == {
                "think",
                "file_io",
            }
        )
        bound_names = {
            s["name"]
            for s in filter_registry_schemas(
                registry.get_schemas(), gate.bound_tool_names
            )
        }
        for privileged in ("shell", "web_search", "task", "state_file", "state_todo"):
            assert privileged not in bound_names

    def test_coach_config_fails_fast_when_registry_lacks_declared_tool(self) -> None:
        """FR-5 failure path FIRST: registry without file_io stops the build."""
        from services.governance.subject_coach_identity import (
            SUBJECT_COACH_CAPABILITIES,
            subject_coach_agent_config,
        )

        crippled = ToolRegistry({"think": ToolDefinition(executor=_stub, schema=_Noop)})
        with pytest.raises(CapabilityToolMissingError):
            build_graph(
                agent_config=subject_coach_agent_config(),
                tool_registry=crippled,
                bound_capabilities=SUBJECT_COACH_CAPABILITIES,
            )

    def test_coach_config_builds_with_gating_enabled(self) -> None:
        """The coach AgentConfig factory ships with capability gating ON
        (shadow-first is about judge/gate flags, not the identity contract)."""
        from services.governance.subject_coach_identity import (
            SUBJECT_COACH_AGENT_ID,
            SUBJECT_COACH_CAPABILITIES,
            subject_coach_agent_config,
        )

        cfg = subject_coach_agent_config()
        assert cfg.capability_gating_enabled is True
        assert cfg.agent_name == SUBJECT_COACH_AGENT_ID
        # End-to-end: builds clean against the production tool vocabulary.
        build_graph(
            agent_config=cfg,
            tool_registry=_production_shaped_registry(),
            bound_capabilities=SUBJECT_COACH_CAPABILITIES,
        )
