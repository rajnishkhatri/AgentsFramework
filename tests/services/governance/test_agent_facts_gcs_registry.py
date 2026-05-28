"""Tests for AgentFactsGcsRegistry.

Failure paths first (TAP-4):
  - Missing secret → ValueError at construction
  - Agent not found → KeyError
  - Duplicate register → ValueError
  - Verify on tampered data → False
  - Happy path: register → get → verify round-trip
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from services.governance.agent_facts_gcs_registry import AgentFactsGcsRegistry
from trust.enums import IdentityStatus
from trust.models import AgentFacts, Capability


def _make_facts(agent_id: str = "agent-1") -> AgentFacts:
    return AgentFacts(
        agent_id=agent_id,
        agent_name="Test Agent",
        owner="test-user",
        version="1.0.0",
        description="A test agent",
        capabilities=[Capability(name="test.cap")],
        status=IdentityStatus.ACTIVE,
    )


def _make_mock_client():
    """Create a mock GCS client with in-memory blob storage."""
    client = MagicMock()
    blobs: dict[str, str] = {}

    def _make_blob(key):
        blob = MagicMock()
        blob.name = key

        def exists():
            return key in blobs

        def upload_from_string(data, content_type=None):
            blobs[key] = data

        def download_as_text():
            if key not in blobs:
                raise Exception(f"Blob {key} not found")
            return blobs[key]

        blob.exists = exists
        blob.upload_from_string = upload_from_string
        blob.download_as_text = download_as_text
        return blob

    bucket = MagicMock()
    bucket.blob = _make_blob

    def _list_blobs(prefix=""):
        result = []
        for k in blobs:
            if k.startswith(prefix):
                b = MagicMock()
                b.name = k
                result.append(b)
        return result

    bucket.list_blobs = _list_blobs
    client.bucket.return_value = bucket
    client._blobs = blobs
    return client


class TestAgentFactsGcsRegistryFailurePaths:
    def test_missing_secret_raises_value_error(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="requires a secret"):
                AgentFactsGcsRegistry("bucket", secret=None, client=MagicMock())

    def test_get_nonexistent_agent_raises_key_error(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent-agent")

    def test_register_duplicate_raises_value_error(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        facts = _make_facts("agent-dup")
        registry.register(facts, registered_by="admin")

        with pytest.raises(ValueError, match="already registered"):
            registry.register(facts, registered_by="admin")

    def test_verify_returns_false_for_missing_agent(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        assert registry.verify("nonexistent") is False


class TestAgentFactsGcsRegistryHappyPath:
    def test_register_get_round_trip(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        facts = _make_facts("agent-rt")
        registered = registry.register(facts, registered_by="admin")

        assert registered.signature_hash is not None
        assert registered.agent_id == "agent-rt"

        retrieved = registry.get("agent-rt")
        assert retrieved.agent_id == "agent-rt"
        assert retrieved.signature_hash == registered.signature_hash

    def test_verify_returns_true_for_valid_registration(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        facts = _make_facts("agent-v")
        registry.register(facts, registered_by="admin")

        assert registry.verify("agent-v") is True

    def test_verify_returns_false_after_suspend(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        facts = _make_facts("agent-s")
        registry.register(facts, registered_by="admin")
        registry.suspend("agent-s", reason="test", suspended_by="admin")

        assert registry.verify("agent-s") is False

    def test_restore_after_suspend_re_enables_verify(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        facts = _make_facts("agent-r")
        registry.register(facts, registered_by="admin")
        registry.suspend("agent-r", reason="test", suspended_by="admin")
        registry.restore("agent-r", reason="restored", restored_by="admin")

        assert registry.verify("agent-r") is True

    def test_list_agent_ids(self) -> None:
        mock_client = _make_mock_client()
        registry = AgentFactsGcsRegistry(
            "bucket", secret="test-secret", client=mock_client
        )
        registry.register(_make_facts("agent-b"), registered_by="admin")
        registry.register(_make_facts("agent-a"), registered_by="admin")

        ids = registry.list_agent_ids()
        assert ids == ["agent-a", "agent-b"]

    def test_verify_false_with_wrong_secret(self) -> None:
        mock_client = _make_mock_client()
        registry_write = AgentFactsGcsRegistry(
            "bucket", secret="secret-1", client=mock_client
        )
        registry_write.register(_make_facts("agent-ws"), registered_by="admin")

        registry_read = AgentFactsGcsRegistry(
            "bucket", secret="secret-2", client=mock_client
        )
        assert registry_read.verify("agent-ws") is False
