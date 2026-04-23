"""US-8.4 — frontend/lib/README.md MUST document the sealed-envelope rule.

This is the human-facing complement to ``test_sealed_envelope.py``: the
runtime guarantee that ``verify_signature(...)`` rejects mutated
payloads is only useful if frontend authors KNOW they must pass signed
payloads through unchanged. This test fails if the README is missing or
omits the sealed-envelope contract.

Per AGENT_UI_ADAPTER_PLAN.md §4.4 / risk R3.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "frontend" / "lib" / "README.md"


def test_readme_exists() -> None:
    assert README.exists(), (
        f"frontend/lib/README.md not committed at {README} -- US-8.4 owes it."
    )


def test_readme_documents_sealed_envelope_rule() -> None:
    text = README.read_text().lower()
    assert "sealed envelope" in text or "sealed-envelope" in text, (
        "README must use the term 'sealed envelope' so frontend authors "
        "find the rule by searching."
    )
    assert "agentfacts" in text, (
        "README must call out AgentFacts as a sealed-envelope type."
    )
    assert "trusttracerecord" in text, (
        "README must call out TrustTraceRecord as a sealed-envelope type."
    )
    assert "policydecision" in text, (
        "README must call out PolicyDecision as a sealed-envelope type."
    )


def test_readme_states_passthrough_requirement() -> None:
    text = README.read_text().lower()
    indicators = ("passed through", "pass through", "unchanged", "bytewise")
    assert any(ind in text for ind in indicators), (
        "README must state the bytes-unchanged passthrough requirement."
    )


def test_readme_points_at_regen_script() -> None:
    text = README.read_text()
    assert "regenerate_wire_artifacts" in text, (
        "README must tell frontend authors how to regenerate the artifacts."
    )
