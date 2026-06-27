"""Regression guard: the LOCAL dev runner (``python -m middleware``) builds its
graph + runtime from the FULL components bag, so ``memory_service`` and the
Phase-2 ``memory_autocapture`` actually reach ``LangGraphRuntime``.

Why this file exists
--------------------
``build_dev_app`` once hand-rebuilt a narrow ``AgentComponents`` from the slimmed
5-tuple ``_build_base_components`` (agent_config / tool_registry /
agent_facts_registry / cache_dir / goal_judge_config_reader / settings) and
passed THAT to the runtime — silently dropping ``memory_autocapture`` (it fell
back to the dataclass ``None`` default). The result: locally,
``MEMORY_AUTOCAPTURE_ENABLED=true`` had no effect — the runtime got
``autocapture=None`` and never stored a thing, regardless of the flag or a valid
enable-policy certificate. This is the dev-side twin of the prod bug guarded by
``test_app_prod_memory_wiring.py``.

This guard pins the dev assembly: whatever ``_build_agent_components`` returns is
the SAME bag whose ``memory_autocapture`` reaches ``LangGraphRuntime``.
"""

from __future__ import annotations

import os
from importlib import reload
from pathlib import Path
from unittest.mock import MagicMock, patch

from trust.models import AgentFacts, Capability, IdentityStatus


def _boot_dev_app_capturing_runtime():
    """Boot ``build_dev_app`` with deps mocked; return the kwargs the runtime
    (``LangGraphRuntime``) was actually constructed with."""
    from middleware.composition import AgentComponents

    sentinel_autocapture = MagicMock(name="memory_autocapture")
    sentinel_memory = MagicMock(name="memory_service")

    dev_identity = AgentFacts(
        agent_id="dev-agent",
        agent_name="Dev Agent",
        owner="dev-user",
        version="1.0.0",
        description="Local development agent",
        capabilities=[Capability(name="delegate.subagent.*")],
        status=IdentityStatus.ACTIVE,
    )
    registry = MagicMock()
    registry.get.return_value = dev_identity

    full_bag = AgentComponents(
        agent_config=MagicMock(),
        tool_registry=MagicMock(),
        agent_facts_registry=registry,
        cache_dir=Path("/tmp/agent-dev-wiring-test"),
        goal_judge_config_reader=MagicMock(),
        settings=MagicMock(),
        memory_service=sentinel_memory,
        memory_autocapture=sentinel_autocapture,
    )

    captured: dict = {}

    def _spy_runtime(*args, **kwargs):
        captured.update(kwargs)
        return MagicMock(name="runtime")

    import middleware.__main__ as mod

    reload(mod)

    with (
        patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}, clear=False),
        patch.object(mod, "_GCP_EXECUTION_ENV", None),
        patch.object(mod, "_build_agent_components", return_value=full_bag),
        patch.object(mod, "_load_graph_factory", return_value=MagicMock()),
        patch.object(mod, "build_runtime_graph", return_value=MagicMock()),
        patch.object(mod, "LangGraphRuntime", side_effect=_spy_runtime),
        patch.object(mod, "TraceService", return_value=MagicMock()),
        patch.object(mod, "JsonlFileTraceSink", return_value=MagicMock()),
    ):
        app = mod.build_dev_app()
        # Enter the lifespan so the graph + runtime are constructed.
        from fastapi.testclient import TestClient

        with TestClient(app):
            pass

    return captured, sentinel_autocapture, sentinel_memory


def test_dev_runtime_receives_wired_autocapture() -> None:
    captured, sentinel_autocapture, _ = _boot_dev_app_capturing_runtime()
    assert "autocapture" in captured, "LangGraphRuntime was never constructed"
    assert captured["autocapture"] is sentinel_autocapture, (
        "the dev runtime got an autocapture that is not the wired service — "
        "MEMORY_AUTOCAPTURE_ENABLED would be a no-op locally"
    )
    assert captured["autocapture"] is not None
