"""Tests for GcpIdentityResolver.

Failure paths first (TAP-4):
  - No env vars + metadata unreachable → RuntimeError
  - Resolved agent_id not in registry → KeyError
  - Happy path: GCP_AGENT_ID override
  - Happy path: GCP_SERVICE_ACCOUNT mapping
  - Happy path: SA email convention (local part as agent_id)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.cloud_providers.gcp_identity import GcpIdentityResolver
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability


def _make_facts(agent_id: str) -> AgentFacts:
    return AgentFacts(
        agent_id=agent_id,
        agent_name=f"Agent {agent_id}",
        owner="test-user",
        version="1.0.0",
        description="test",
        capabilities=[Capability(name="test")],
        status=IdentityStatus.ACTIVE,
    )


def _make_registry(agents: dict[str, AgentFacts]) -> MagicMock:
    registry = MagicMock()

    def get(agent_id: str) -> AgentFacts:
        if agent_id not in agents:
            raise KeyError(f"Agent '{agent_id}' not found")
        return agents[agent_id]

    registry.get = get
    return registry


class TestGcpIdentityResolverFailurePaths:
    def test_no_env_no_metadata_raises_runtime_error(self) -> None:
        registry = _make_registry({})
        resolver = GcpIdentityResolver(registry)

        with patch.dict("os.environ", {}, clear=True):
            with patch.object(
                GcpIdentityResolver, "_query_metadata_server", return_value=None
            ):
                with pytest.raises(RuntimeError, match="Cannot resolve GCP identity"):
                    resolver.resolve()

    def test_resolved_agent_not_in_registry_raises_key_error(self) -> None:
        registry = _make_registry({})
        resolver = GcpIdentityResolver(registry)

        with patch.dict("os.environ", {"GCP_AGENT_ID": "nonexistent"}):
            with pytest.raises(KeyError, match="nonexistent"):
                resolver.resolve()


class TestGcpIdentityResolverHappyPath:
    def test_explicit_agent_id_override(self) -> None:
        facts = _make_facts("explicit-agent")
        registry = _make_registry({"explicit-agent": facts})
        resolver = GcpIdentityResolver(registry)

        with patch.dict("os.environ", {"GCP_AGENT_ID": "explicit-agent"}):
            result = resolver.resolve()

        assert result.agent_id == "explicit-agent"

    def test_service_account_with_explicit_mapping(self) -> None:
        facts = _make_facts("backend-agent")
        registry = _make_registry({"backend-agent": facts})
        resolver = GcpIdentityResolver(
            registry,
            sa_to_agent_id={
                "agent-backend-runtime@my-project.iam.gserviceaccount.com": "backend-agent"
            },
        )

        env = {"GCP_SERVICE_ACCOUNT": "agent-backend-runtime@my-project.iam.gserviceaccount.com"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(
                GcpIdentityResolver, "_query_metadata_server", return_value=None
            ):
                result = resolver.resolve()

        assert result.agent_id == "backend-agent"

    def test_service_account_convention_uses_local_part(self) -> None:
        facts = _make_facts("agent-backend-runtime")
        registry = _make_registry({"agent-backend-runtime": facts})
        resolver = GcpIdentityResolver(registry)

        env = {"GCP_SERVICE_ACCOUNT": "agent-backend-runtime@my-project.iam.gserviceaccount.com"}
        with patch.dict("os.environ", env, clear=True):
            with patch.object(
                GcpIdentityResolver, "_query_metadata_server", return_value=None
            ):
                result = resolver.resolve()

        assert result.agent_id == "agent-backend-runtime"

    def test_metadata_server_fallback(self) -> None:
        facts = _make_facts("compute-sa")
        registry = _make_registry({"compute-sa": facts})
        resolver = GcpIdentityResolver(registry)

        with patch.dict("os.environ", {}, clear=True):
            with patch.object(
                GcpIdentityResolver,
                "_query_metadata_server",
                return_value="compute-sa@project.iam.gserviceaccount.com",
            ):
                result = resolver.resolve()

        assert result.agent_id == "compute-sa"

    def test_gcp_agent_id_takes_priority_over_service_account(self) -> None:
        facts_explicit = _make_facts("priority-agent")
        facts_sa = _make_facts("sa-agent")
        registry = _make_registry({
            "priority-agent": facts_explicit,
            "sa-agent": facts_sa,
        })
        resolver = GcpIdentityResolver(registry)

        env = {
            "GCP_AGENT_ID": "priority-agent",
            "GCP_SERVICE_ACCOUNT": "sa-agent@project.iam.gserviceaccount.com",
        }
        with patch.dict("os.environ", env):
            result = resolver.resolve()

        assert result.agent_id == "priority-agent"
