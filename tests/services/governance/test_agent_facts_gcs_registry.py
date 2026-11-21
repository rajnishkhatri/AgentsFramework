"""Tests for AgentFactsGcsRegistry.

Failure paths first (TAP-4):
  - Missing secret → ValueError at construction
  - Agent not found → KeyError
  - Duplicate register → ValueError
  - Verify on tampered data → False
  - Happy path: register → get → verify round-trip
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    """Create a mock GCS client with in-memory blob storage.

    Models object generations so ``if_generation_match`` preconditions behave
    like GCS: 0 means "must not exist", N means "must still be generation N".
    """
    from google.api_core.exceptions import PreconditionFailed

    client = MagicMock()
    blobs: dict[str, str] = {}
    generations: dict[str, int] = {}

    def _make_blob(key):
        blob = MagicMock()
        blob.name = key

        def exists():
            return key in blobs

        def upload_from_string(data, content_type=None, if_generation_match=None):
            current = generations.get(key, 0)
            if if_generation_match is not None and if_generation_match != current:
                raise PreconditionFailed(f"generation mismatch for {key}")
            blobs[key] = data
            generations[key] = current + 1

        def download_as_text():
            if key not in blobs:
                raise Exception(f"Blob {key} not found")
            return blobs[key]

        def reload():
            blob.generation = generations.get(key, 0)

        blob.exists = exists
        blob.upload_from_string = upload_from_string
        blob.download_as_text = download_as_text
        blob.reload = reload
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
    client._generations = generations
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


def test_should_fail_gcs_verification_when_card_expired() -> None:
    from datetime import UTC, datetime, timedelta

    registry = AgentFactsGcsRegistry(
        "bucket", secret="test-secret", client=_make_mock_client()
    )
    expired = _make_facts("agent-expired").model_copy(
        update={"valid_until": datetime.now(UTC) - timedelta(days=1)}
    )
    registry.register(expired, registered_by="admin")

    assert registry.verify("agent-expired") is False


def test_should_fail_gcs_verification_when_card_blob_is_corrupt() -> None:
    client = _make_mock_client()
    registry = AgentFactsGcsRegistry("bucket", secret="test-secret", client=client)
    registry.register(_make_facts("agent-corrupt"), registered_by="admin")
    client._blobs["agent_facts/agent-corrupt.json"] = "{not json"

    assert registry.verify("agent-corrupt") is False


def test_should_refuse_register_when_card_appears_after_existence_check() -> None:
    """A concurrent register must not be silently overwritten."""
    client = _make_mock_client()
    registry = AgentFactsGcsRegistry("bucket", secret="test-secret", client=client)
    registry.register(_make_facts("agent-race"), registered_by="first")
    original = client._blobs["agent_facts/agent-race.json"]

    # Simulate the stale read a racing writer would see: the blob "did not
    # exist" at check time even though the first writer has since created it.
    real_blob = client.bucket.return_value.blob

    def _stale_blob(key):
        blob = real_blob(key)
        if key.endswith("agent-race.json"):
            blob.exists = lambda: False
        return blob

    client.bucket.return_value.blob = _stale_blob

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_make_facts("agent-race"), registered_by="second")
    assert client._blobs["agent_facts/agent-race.json"] == original


def test_should_keep_both_audit_entries_when_append_conflicts() -> None:
    """A concurrent audit append must be retried, not lost."""
    client = _make_mock_client()
    registry = AgentFactsGcsRegistry("bucket", secret="test-secret", client=client)
    registry.register(_make_facts("agent-audit"), registered_by="admin")
    audit_key = "agent_facts/agent-audit_audit.jsonl"

    real_blob = client.bucket.return_value.blob
    injected = {"done": False}

    def _racing_blob(key):
        blob = real_blob(key)
        if key == audit_key and not injected["done"]:
            real_download = blob.download_as_text

            def _download_then_race():
                text = real_download()
                if not injected["done"]:
                    injected["done"] = True
                    # Another writer lands between our read and our write.
                    client._blobs[audit_key] = text + '{"concurrent": true}\n'
                    client._generations[audit_key] += 1
                return text

            blob.download_as_text = _download_then_race
        return blob

    client.bucket.return_value.blob = _racing_blob

    registry.suspend("agent-audit", reason="test", suspended_by="admin")

    lines = client._blobs[audit_key].splitlines()
    assert len(lines) == 3
    assert '{"concurrent": true}' in lines
    assert '"action":"suspend"' in lines[-1]
