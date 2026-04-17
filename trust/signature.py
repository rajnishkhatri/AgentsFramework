"""Signature computation and verification for AgentFacts.

Uses HMAC-SHA256 over a canonical JSON representation to produce
deterministic, tamper-evident hashes. Pure stdlib -- no I/O, no
cloud imports.
"""

from __future__ import annotations

import hashlib
import hmac
import json


def compute_signature(facts_dict: dict, secret: str) -> str:
    """Compute HMAC-SHA256 over canonical (sorted-key) JSON of agent facts."""
    canonical = json.dumps(facts_dict, sort_keys=True, default=str)
    return hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(facts_dict: dict, secret: str, expected_hash: str) -> bool:
    """Verify a signature hash matches the expected value (constant-time)."""
    actual = compute_signature(facts_dict, secret)
    return hmac.compare_digest(actual, expected_hash)
