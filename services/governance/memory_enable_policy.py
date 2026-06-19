"""The autocapture write-back ENABLE-POLICY guard.

This is the machine-checkable link between the calibration scorer
(:mod:`services.governance.memory_extractor_calibration`) and the runtime flag
``MEMORY_AUTOCAPTURE_ENABLED``. The enable-policy doc
(``docs/recipes/memory_extractor/03_enable_policy.md``) says *"the flag is the
gate"* — historically that was an **honour-system** procedure (a human runs the
CLI, reads ``ENABLE-ELIGIBLE``, then flips the env var). Nothing stopped a prod
deploy from setting the flag without ever clearing the gate.

This module turns that procedure into an **invariant enforced in code**:
write-back turns on only when BOTH

  1. the operator's intent is present (``flag_requested`` —
     ``MEMORY_AUTOCAPTURE_ENABLED=true``), AND
  2. a **passing, frozen test-split** calibration certificate is present and
     re-validated here.

If the flag is on but no valid certificate is found, the guard **fails safe to
shadow** (propose-only — never store ungated) and reports exactly why, so the
composition root can log a loud governance warning. Flag off is the silent
default (cardinal rule 6: default-off until calibrated); rollback is unchanged
(flag off → shadow instantly).

Framework-clean (I-4): no ``langgraph``/``langchain``; pure dataclasses + a
single defensive JSON read. The certificate is what the calibration CLI emits
on a passing run (``scripts/eval/memory_extractor_calibrate.py
--emit-certificate``) — derived from the same :class:`CalibrationReport`, so the
scorer stays the single source of the gate math. This guard only re-checks the
emitted result; it does not re-implement the metrics (TAP-1).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("services.governance.memory_enable_policy")

# Schema tag stamped into the certificate; a mismatch (older/foreign file) fails
# safe to None so a stale artifact can never silently enable write-back.
CERT_SCHEMA = "memory-autocapture-enable-cert-v1"

# Only the FROZEN test split clears the gate. A dev-split certificate never
# enables (AP-4: never enable off the iterating split). 03_enable_policy.md §1.
REQUIRED_SPLIT = "test"

# Every gate the scorer emits must individually pass (defense in depth — we do
# not trust a top-level ``passed`` that a hand-edited file could fake). These
# names mirror memory_extractor_calibration.score()'s GateResult names; the PII
# flip-rate gate is the hard-zero content-leak guard.
REQUIRED_GATES = frozenset(
    {
        "store_class_precision",
        "false_store_on_trivia",
        "mistype_rate",
        "pii_flip_rate",
        "kappa_judge_vs_gold",
    }
)

__all__ = [
    "CERT_SCHEMA",
    "REQUIRED_SPLIT",
    "REQUIRED_GATES",
    "EnablePolicyCertificate",
    "WriteBackDecision",
    "load_certificate",
    "resolve_write_back",
]


@dataclass(frozen=True)
class EnablePolicyCertificate:
    """A calibration run's verdict, persisted so the runtime can re-check it.

    Counts and pass/fail only — never gold content, never proposals. The
    ``gates`` map is ``{gate_name: passed}`` so the guard can re-validate each
    one (not just the rolled-up ``passed``).
    """

    schema: str
    passed: bool
    split: str
    total_rows: int
    gates: dict[str, bool]
    gold_sha256: str = ""
    scored_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EnablePolicyCertificate:
        gates_raw = payload.get("gates") or []
        # Accept either the rich GateResult list (CLI output) or a flat map.
        if isinstance(gates_raw, dict):
            gates = {str(k): bool(v) for k, v in gates_raw.items()}
        else:
            gates = {
                str(g.get("name")): bool(g.get("passed"))
                for g in gates_raw
                if g.get("name") is not None
            }
        return cls(
            schema=str(payload.get("schema", "")),
            passed=bool(payload.get("passed", False)),
            split=str(payload.get("split", "")),
            total_rows=int(payload.get("total_rows", 0)),
            gates=gates,
            gold_sha256=str(payload.get("gold_sha256", "")),
            scored_at=str(payload.get("scored_at", "")),
        )


@dataclass(frozen=True)
class WriteBackDecision:
    """The resolved write-back posture + an auditable reason.

    ``write_back_enabled`` is what the composition root passes to
    ``MemoryAutoCaptureService``. ``blocked`` is True only when the operator
    *requested* write-back but the gate refused — the case the composition root
    logs at WARNING (an intent that did not clear governance).
    """

    write_back_enabled: bool
    requested: bool
    reason: str
    certificate: EnablePolicyCertificate | None = None

    @property
    def blocked(self) -> bool:
        return self.requested and not self.write_back_enabled


def load_certificate(path: Path | str | None) -> EnablePolicyCertificate | None:
    """Load + schema-check a certificate. Fails SAFE to None on any problem.

    Returns None for: a None path, a missing file, malformed JSON, or a schema
    mismatch. None means "no valid certificate" → the guard keeps shadow. A
    corrupt certificate must never crash composition nor enable write-back.
    """
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning(
            "memory enable-policy: certificate at %s is unreadable/corrupt — "
            "treating as ABSENT (write-back stays shadow).",
            p,
        )
        return None
    if not isinstance(payload, dict):
        return None
    cert = EnablePolicyCertificate.from_dict(payload)
    if cert.schema != CERT_SCHEMA:
        logger.warning(
            "memory enable-policy: certificate schema %r != %r — treating as "
            "ABSENT (write-back stays shadow).",
            cert.schema,
            CERT_SCHEMA,
        )
        return None
    return cert


def _certificate_clears(cert: EnablePolicyCertificate) -> tuple[bool, str]:
    """Re-validate a loaded certificate against the enable-policy invariants.

    Returns ``(clears, reason)``. We re-check the split, the top-level verdict,
    AND every required gate individually — so a hand-edited ``passed: true`` over
    a failed hard-zero gate is still rejected.
    """
    if cert.split != REQUIRED_SPLIT:
        return (
            False,
            f"certificate split={cert.split!r} is not the frozen "
            f"{REQUIRED_SPLIT!r} split (03_enable_policy §1).",
        )
    if not cert.passed:
        return False, "certificate verdict did not pass (BLOCKED)."
    missing = REQUIRED_GATES - cert.gates.keys()
    if missing:
        return (
            False,
            f"certificate is missing required gate(s): {sorted(missing)}.",
        )
    failed = sorted(g for g in REQUIRED_GATES if not cert.gates.get(g, False))
    if failed:
        return False, f"certificate gate(s) failed: {failed}."
    return (
        True,
        f"calibration certificate cleared on the frozen {REQUIRED_SPLIT!r} "
        f"split (rows={cert.total_rows}, gold={cert.gold_sha256[:8] or '?'}).",
    )


def resolve_write_back(
    *,
    flag_requested: bool,
    certificate: EnablePolicyCertificate | None,
) -> WriteBackDecision:
    """Decide the effective write-back posture from intent + certificate.

    Truth table:

      flag | cert          | write-back | note
      -----|---------------|------------|-------------------------------------
      off  | (any)         | OFF        | default shadow; not blocked
      on   | None          | OFF        | BLOCKED — flag set but gate never run
      on   | failing/wrong | OFF        | BLOCKED — gate did not clear
      on   | passing+test  | ON         | enabled
    """
    if not flag_requested:
        return WriteBackDecision(
            write_back_enabled=False,
            requested=False,
            reason="MEMORY_AUTOCAPTURE_ENABLED is off — shadow (propose-only).",
            certificate=certificate,
        )
    if certificate is None:
        return WriteBackDecision(
            write_back_enabled=False,
            requested=True,
            reason=(
                "MEMORY_AUTOCAPTURE_ENABLED is on but no calibration certificate "
                "is present (MEMORY_AUTOCAPTURE_CERT unset/invalid) — write-back "
                "stays SHADOW. Run scripts/eval/memory_extractor_calibrate.py "
                "--emit-certificate on the frozen test split first."
            ),
            certificate=None,
        )
    clears, why = _certificate_clears(certificate)
    if not clears:
        return WriteBackDecision(
            write_back_enabled=False,
            requested=True,
            reason=f"write-back stays SHADOW: {why}",
            certificate=certificate,
        )
    return WriteBackDecision(
        write_back_enabled=True,
        requested=True,
        reason=f"write-back ENABLED: {why}",
        certificate=certificate,
    )
