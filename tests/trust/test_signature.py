"""Tests for trust/signature.py -- compute and verify signatures."""

from __future__ import annotations

from trust.signature import compute_signature, verify_signature


class TestComputeSignature:
    def test_returns_hex_string(self):
        result = compute_signature({"agent_id": "a1"}, "secret")
        assert isinstance(result, str), (
            "compute_signature must return a str (hex digest)"
        )
        assert len(result) == 64, (
            "compute_signature must return a 64-char SHA-256 hex digest"
        )

    def test_deterministic(self):
        data = {"agent_id": "a1", "version": "1.0"}
        sig1 = compute_signature(data, "secret")
        sig2 = compute_signature(data, "secret")
        assert sig1 == sig2, (
            "compute_signature must be deterministic for identical (data, secret)"
        )

    def test_different_data_produces_different_signatures(self):
        sig1 = compute_signature({"agent_id": "a1"}, "secret")
        sig2 = compute_signature({"agent_id": "a2"}, "secret")
        assert sig1 != sig2, (
            "compute_signature must yield distinct digests for distinct data"
        )

    def test_different_secrets_produce_different_signatures(self):
        data = {"agent_id": "a1"}
        sig1 = compute_signature(data, "secret1")
        sig2 = compute_signature(data, "secret2")
        assert sig1 != sig2, (
            "compute_signature must yield distinct digests for distinct secrets"
        )

    def test_key_order_does_not_matter(self):
        """JSON is sorted by keys, so insertion order is irrelevant."""
        sig1 = compute_signature({"b": 2, "a": 1}, "secret")
        sig2 = compute_signature({"a": 1, "b": 2}, "secret")
        assert sig1 == sig2, (
            "compute_signature must be insensitive to dict insertion order "
            "(JSON keys are sorted)"
        )


class TestVerifySignature:
    def test_valid_signature_returns_true(self):
        data = {"agent_id": "a1", "version": "1.0"}
        secret = "my-secret"
        sig = compute_signature(data, secret)
        assert verify_signature(data, secret, sig) is True, (
            "verify_signature must return True for an unmodified signed payload"
        )

    def test_tampered_data_returns_false(self):
        data = {"agent_id": "a1"}
        secret = "my-secret"
        sig = compute_signature(data, secret)
        tampered = {"agent_id": "a1-tampered"}
        assert verify_signature(tampered, secret, sig) is False, (
            "verify_signature must return False when the data is tampered"
        )

    def test_wrong_secret_returns_false(self):
        data = {"agent_id": "a1"}
        sig = compute_signature(data, "correct-secret")
        assert verify_signature(data, "wrong-secret", sig) is False, (
            "verify_signature must return False when the secret is incorrect"
        )

    def test_corrupted_hash_returns_false(self):
        data = {"agent_id": "a1"}
        secret = "my-secret"
        assert verify_signature(data, secret, "0" * 64) is False, (
            "verify_signature must return False for a corrupted digest"
        )

    def test_roundtrip(self):
        data = {
            "agent_id": "writer-001",
            "agent_name": "TestBot",
            "owner": "team-alpha",
            "version": "2.1.0",
            "capabilities": ["read", "write"],
        }
        secret = "production-signing-key"
        sig = compute_signature(data, secret)
        assert verify_signature(data, secret, sig) is True, (
            "compute_signature -> verify_signature must round-trip for a rich payload"
        )
