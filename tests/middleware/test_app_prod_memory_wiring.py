"""Regression guard: the prod combined app builds its graph from the FULL
components bag, so memory_service + memory_autocapture actually reach the loop.

Why this file exists
--------------------
``build_combined_app`` once hand-rebuilt a narrow ``AgentComponents`` (copying
agent_config / tool_registry / agent_facts_registry / cache_dir /
goal_judge_config_reader / settings) and passed THAT to ``build_runtime_graph``
— silently dropping ``memory_service`` and ``memory_autocapture`` (both fell
back to the dataclass ``None`` default). The graph compiled memory-blind, so on
the live ``mem`` tag — flag on, real user_id, durable Mem0 backend — recall and
store NEVER fired and emitted zero carriers. The existing wiring suite
(``tests/orchestration/test_memory_wiring.py``) missed it because those tests
call ``build_graph(memory_service=...)`` directly, bypassing this prod assembly.

This guard pins the prod assembly itself: whatever ``_build_agent_components``
returns is the SAME bag the graph is built from, with memory_service intact.
"""

from __future__ import annotations

import os
from importlib import reload
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


_PROD_ENV = {
    "AGENT_ENV": "prod",
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


def _build_app_capturing_graph_components():
    """Boot the prod app with GCP deps mocked; return the ``components`` object
    that ``build_runtime_graph`` was actually called with."""
    sentinel_memory = MagicMock(name="memory_service")
    sentinel_autocapture = MagicMock(name="memory_autocapture")

    full_bag = MagicMock(name="full_components")
    full_bag.memory_service = sentinel_memory
    full_bag.memory_autocapture = sentinel_autocapture
    # goal_judge reader needs a real-ish health posture for the cache-warm path.
    reader = MagicMock()
    reader.health_posture.return_value = {
        "enabled": False,
        "downgrade_enabled": False,
        "source": "default",
    }
    full_bag.goal_judge_config_reader = reader
    full_bag.agent_facts_registry = MagicMock()
    full_bag.cache_dir = Path("/tmp/agent-cache")

    five_tuple = (
        MagicMock(),  # agent_config (discarded by build_combined_app)
        MagicMock(),  # tool_registry (discarded)
        full_bag.agent_facts_registry,
        full_bag.cache_dir,
        reader,
    )

    captured: dict = {}

    def _spy_build_runtime_graph(components, build_graph, **kwargs):
        captured["components"] = components
        return MagicMock(name="graph")

    # The graph is compiled inside the FastAPI lifespan, which first enters
    # PostgresCheckpointer.from_env() (an async ctx mgr). Mock it so startup
    # reaches build_runtime_graph without a real DB; it is imported inside the
    # lifespan, so patch it at its source module.
    pg_cp = MagicMock()
    pg_cp.saver = MagicMock()
    pg_cm = MagicMock()
    pg_cm.__aenter__ = AsyncMock(return_value=pg_cp)
    pg_cm.__aexit__ = AsyncMock(return_value=False)

    # Reload FIRST, then patch the reloaded module: reload() re-executes the
    # import statements and would otherwise clobber any string-target patches
    # applied to middleware.app_prod attributes before it ran.
    import middleware.app_prod as mod

    reload(mod)

    with patch.dict(os.environ, _PROD_ENV, clear=False), \
         patch.object(mod, "GcsTraceSink", return_value=MagicMock()), \
         patch.object(mod, "_load_graph_factory", return_value=MagicMock()), \
         patch.object(mod, "build_runtime_graph", side_effect=_spy_build_runtime_graph), \
         patch.object(mod, "LangGraphRuntime", return_value=MagicMock()), \
         patch.object(
             mod, "build_adapters",
             return_value=MagicMock(profile="v3", black_box_relay=None),
         ), \
         patch(
             "agent_ui_adapter.adapters.runtime.postgres_saver.PostgresCheckpointer.from_env",
             return_value=pg_cm,
         ), \
         patch.object(mod, "_build_components", return_value=five_tuple), \
         patch.object(mod, "_build_agent_components", return_value=full_bag):
        app = mod.build_combined_app()
        # Enter the lifespan so build_runtime_graph runs.
        from fastapi.testclient import TestClient

        with TestClient(app):
            pass

    return captured, sentinel_memory, sentinel_autocapture


def test_graph_built_from_full_bag_with_memory_service() -> None:
    captured, sentinel_memory, _ = _build_app_capturing_graph_components()
    assert "components" in captured, "build_runtime_graph was never called"
    bag = captured["components"]
    assert bag.memory_service is sentinel_memory, (
        "the prod graph was built from a bag whose memory_service is not the "
        "wired service — recall/store will be dead in prod"
    )
    assert bag.memory_service is not None


def test_graph_bag_carries_autocapture() -> None:
    captured, _, sentinel_autocapture = _build_app_capturing_graph_components()
    bag = captured["components"]
    assert bag.memory_autocapture is sentinel_autocapture
