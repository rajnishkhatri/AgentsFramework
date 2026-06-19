"""L2 Reproducible: the autocapture write-back enable-policy GUARD.

Failure paths first (TAP-4). This is the machine-checkable link between the
calibration scorer (``memory_extractor_calibration``) and the runtime flag
(``MEMORY_AUTOCAPTURE_ENABLED``). The doc (03_enable_policy.md) says "the flag
is the gate" — this guard makes that an INVARIANT, not an honour-system step:
write-back turns on only when the operator's intent (the flag) AND a passing,
frozen calibration certificate agree. Flag-on-but-no-certificate fails SAFE to
shadow (never store ungated), and the guard says exactly why.

No LLM, no I/O beyond a tmp certificate file — pure policy resolution.
Thresholds and the frozen split live in 03_enable_policy.md §2.
"""

from __future__ import annotations

import json
from pathlib import Path


from services.governance.memory_enable_policy import (
    REQUIRED_SPLIT,
    EnablePolicyCertificate,
    WriteBackDecision,
    load_certificate,
    resolve_write_back,
)


def _cert_dict(
    *,
    passed: bool = True,
    split: str = REQUIRED_SPLIT,
    gates: dict[str, bool] | None = None,
    total_rows: int = 41,
) -> dict:
    """A serialized certificate the CLI would emit on a passing run."""
    if gates is None:
        gates = {
            "store_class_precision": True,
            "false_store_on_trivia": True,
            "mistype_rate": True,
            "pii_flip_rate": True,
            "kappa_judge_vs_gold": True,
        }
    return {
        "schema": "memory-autocapture-enable-cert-v1",
        "passed": passed,
        "split": split,
        "total_rows": total_rows,
        "gates": [
            {"name": n, "passed": p, "value": 1.0, "threshold": 0.9}
            for n, p in gates.items()
        ],
        "gold_sha256": "abc123",
        "scored_at": "2026-06-19T00:00:00Z",
    }


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ── Failure paths first ─────────────────────────────────────────────────


class TestFlagOnButNoCertificateFailsSafe:
    def test_flag_on_no_certificate_stays_shadow(self) -> None:
        # The dangerous case: operator set the env flag but never ran the gate.
        # Must NOT enable write-back — fall back to shadow and say why.
        decision = resolve_write_back(flag_requested=True, certificate=None)
        assert decision.write_back_enabled is False
        assert decision.requested is True
        assert "no calibration certificate" in decision.reason.lower()

    def test_flag_off_no_certificate_is_shadow_silently(self) -> None:
        # Flag off is the default posture; absence of a cert is expected, not a
        # governance alarm.
        decision = resolve_write_back(flag_requested=False, certificate=None)
        assert decision.write_back_enabled is False
        assert decision.requested is False
        assert decision.blocked is False  # nothing was requested → nothing blocked


class TestFlagOnButCertificateFailingFailsSafe:
    def test_flag_on_failing_certificate_stays_shadow(self) -> None:
        cert = EnablePolicyCertificate.from_dict(_cert_dict(passed=False))
        decision = resolve_write_back(flag_requested=True, certificate=cert)
        assert decision.write_back_enabled is False
        assert decision.blocked is True
        assert "did not pass" in decision.reason.lower()

    def test_pii_gate_failed_blocks_even_with_passed_true(self) -> None:
        # Defensive: a hand-edited cert claiming passed=true while a hard-zero
        # gate failed must still be rejected (the guard re-checks per-gate).
        cert = EnablePolicyCertificate.from_dict(
            _cert_dict(passed=True, gates={
                "store_class_precision": True,
                "false_store_on_trivia": True,
                "mistype_rate": True,
                "pii_flip_rate": False,  # hard zero failed
                "kappa_judge_vs_gold": True,
            })
        )
        decision = resolve_write_back(flag_requested=True, certificate=cert)
        assert decision.write_back_enabled is False
        assert decision.blocked is True
        assert "pii_flip_rate" in decision.reason


class TestWrongSplitFailsSafe:
    def test_dev_split_certificate_does_not_enable(self) -> None:
        # Only the FROZEN test split clears the gate (AP-4: never enable off dev).
        cert = EnablePolicyCertificate.from_dict(
            _cert_dict(split="dev")
        )
        decision = resolve_write_back(flag_requested=True, certificate=cert)
        assert decision.write_back_enabled is False
        assert decision.blocked is True
        assert "split" in decision.reason.lower()


class TestLoadCertificateFailureModes:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_certificate(tmp_path / "nope.json") is None

    def test_none_path_returns_none(self) -> None:
        assert load_certificate(None) is None

    def test_malformed_json_returns_none_not_raise(self, tmp_path: Path) -> None:
        bad = tmp_path / "cert.json"
        bad.write_text("{not json", encoding="utf-8")
        # A corrupt cert must fail SAFE (None → shadow), never crash composition.
        assert load_certificate(bad) is None

    def test_wrong_schema_returns_none(self, tmp_path: Path) -> None:
        payload = _cert_dict()
        payload["schema"] = "something-else-v9"
        assert load_certificate(_write(tmp_path / "c.json", payload)) is None


# ── Acceptance ──────────────────────────────────────────────────────────


class TestHappyPathEnables:
    def test_flag_on_passing_test_certificate_enables(self) -> None:
        cert = EnablePolicyCertificate.from_dict(_cert_dict())
        decision = resolve_write_back(flag_requested=True, certificate=cert)
        assert decision.write_back_enabled is True
        assert decision.blocked is False
        assert decision.requested is True

    def test_passing_certificate_but_flag_off_stays_shadow(self) -> None:
        # The certificate alone never enables — the operator must also opt in.
        cert = EnablePolicyCertificate.from_dict(_cert_dict())
        decision = resolve_write_back(flag_requested=False, certificate=cert)
        assert decision.write_back_enabled is False
        assert decision.requested is False

    def test_round_trips_through_disk(self, tmp_path: Path) -> None:
        path = _write(tmp_path / "cert.json", _cert_dict())
        cert = load_certificate(path)
        assert cert is not None
        decision = resolve_write_back(flag_requested=True, certificate=cert)
        assert decision.write_back_enabled is True


class TestDecisionIsAuditable:
    def test_decision_exposes_certificate_provenance(self) -> None:
        cert = EnablePolicyCertificate.from_dict(_cert_dict(total_rows=41))
        decision = resolve_write_back(flag_requested=True, certificate=cert)
        # The composition root logs this — it must name what cleared the gate.
        assert isinstance(decision, WriteBackDecision)
        assert "test" in decision.reason.lower()
        assert "41" in decision.reason or decision.certificate is cert
