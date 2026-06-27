"""Three-band shell-approval PEP (Layer 4 / Orchestration topology gate).

The decide-from-execute Policy Enforcement Point from
``docs/plans/shell_severity_approval_hitl.plan.md`` (Part B, L4). It takes a
command that the L2 :func:`services.governance.shell_severity.classify_severity`
has already tiered into an :class:`~services.governance.shell_severity.ApprovalBand`
and decides — fail-closed — whether the subprocess runs:

* **auto** (LOW)        → execute, no human, no interrupt.
* **ask** (MED/HIGH)    → in enforce mode, fire the injected ``interrupt_fn`` to
  raise the AG-UI approval card; resume with the human decision
  (approve / edit / reject / timeout). In shadow mode, record the carrier and
  run anyway (Phase A — observe severities first).
* **deny** (CRIT)       → hard-deny, un-promptable, even in shadow (a safety
  ceiling, not an enforce toggle).

Every decision emits **exactly one** ``GUARDRAIL_CHECKED`` carrier (one carrier
per fact — the governance audit's cardinal rule). The subprocess (the injected
``execute`` callable) runs **only** on an EXECUTE outcome, strictly *after* the
interrupt resolves, so a node re-execution on resume (the LangChain gotcha) is
naturally idempotent — the classifier may re-run (pure) but the side effect
fires once, post-approval.

``interrupt_fn`` and ``execute`` are injected so this module is unit-tested with
a scripted resume and a fake runner — no live LLM, no live subprocess (Pattern 6
mock provider; Anti-Pattern 3/5). The langgraph ``interrupt()`` is wired in by
the orchestration node that calls this gate, never imported here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from services.governance.shell_severity import ApprovalBand

# Command text is capped before it reaches a carrier (don't ship arbitrary-length
# command bodies onto the trace; the audit only needs an identifying preview).
_COMMAND_CARRIER_CAP = 512

# Severity ordering for the threshold comparison (auto-band promotion).
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class GateOutcome(str, Enum):
    EXECUTED = "executed"  # the (possibly edited) command ran
    DENIED = "denied"  # hard-deny, reject, or fail-closed timeout — never ran


@dataclass(frozen=True)
class ApprovalDecision:
    """The human's resolution returned by ``interrupt_fn`` (the resume value).

    ``decision`` is one of ``approve`` / ``edit`` / ``reject`` / ``timeout``.
    ``edited_command`` is the modify-before-run payload, set only on ``edit``.
    """

    decision: Literal["approve", "edit", "reject", "timeout"]
    edited_command: str | None = None


@dataclass(frozen=True)
class ShellApprovalConfig:
    """The flag subset the gate reads (mirrors the AgentConfig knobs)."""

    enabled: bool
    enforce: bool
    threshold: Literal["low", "medium", "high", "critical"]
    timeout_seconds: int


@dataclass
class GateResult:
    outcome: GateOutcome
    command: str  # the command actually executed (or attempted) — may be edited
    error_class: str | None = None  # "gating" on every non-execute branch
    output: Any = None  # the execute() return on EXECUTE, else None
    carriers: list[dict[str, Any]] = field(default_factory=list)


def _carrier(
    *,
    command: str,
    severity: str,
    band: ApprovalBand,
    decision: str,
    would_enforce: bool,
) -> dict[str, Any]:
    """Build the single GUARDRAIL_CHECKED detail dict (one fact, one carrier)."""
    return {
        "guardrail": "shell_severity",
        "tool": "shell",
        "command": command[:_COMMAND_CARRIER_CAP],
        "severity": severity,
        "band": band.value,
        "decision": decision,
        "would_enforce": would_enforce,
    }


def _at_or_above_threshold(severity: str, threshold: str) -> bool:
    return _SEVERITY_ORDER.get(severity, 99) >= _SEVERITY_ORDER.get(threshold, 0)


def decide_shell_approval(
    *,
    command: str,
    band: ApprovalBand,
    severity: str,
    config: ShellApprovalConfig,
    interrupt_fn: Callable[[dict[str, Any]], ApprovalDecision],
    execute: Callable[[str], Any],
) -> GateResult:
    """Run the three-band PEP and return a :class:`GateResult` (fail-closed).

    ``execute`` is the side-effecting runner; it is called at most once and only
    on an EXECUTE outcome. ``interrupt_fn`` is invoked only when the gate
    actually pauses for a human (enforce mode, ask band) — never for auto/deny.
    """
    # Master flag off → no gate at all; byte-identical to today, no carrier.
    if not config.enabled:
        return GateResult(
            outcome=GateOutcome.EXECUTED,
            command=command,
            output=execute(command),
            carriers=[],
        )

    # DENY ceiling — un-promptable, even in shadow (a safety floor, not a toggle).
    if band is ApprovalBand.DENY:
        carrier = _carrier(
            command=command,
            severity=severity,
            band=band,
            decision="deny",
            would_enforce=True,
        )
        return GateResult(
            outcome=GateOutcome.DENIED,
            command=command,
            error_class="gating",
            carriers=[carrier],
        )

    # AUTO band — execute, no human.
    if band is ApprovalBand.AUTO:
        carrier = _carrier(
            command=command,
            severity=severity,
            band=band,
            decision="auto",
            would_enforce=False,
        )
        return GateResult(
            outcome=GateOutcome.EXECUTED,
            command=command,
            output=execute(command),
            carriers=[carrier],
        )

    # ASK band. Whether it actually pauses depends on the severity threshold and
    # the enforce flag.
    asks = _at_or_above_threshold(severity, config.threshold)

    # Shadow mode (Phase A) or below-threshold: classify + carrier, run anyway.
    if not config.enforce or not asks:
        carrier = _carrier(
            command=command,
            severity=severity,
            band=band,
            decision="shadow_allow",
            would_enforce=asks,
        )
        return GateResult(
            outcome=GateOutcome.EXECUTED,
            command=command,
            output=execute(command),
            carriers=[carrier],
        )

    # Enforce mode, at/above threshold → pause for the human approval card.
    payload = {
        "tool": "shell",
        "command": command[:_COMMAND_CARRIER_CAP],
        "severity": severity,
        "band": band.value,
        "timeout_seconds": config.timeout_seconds,
    }
    resolution = interrupt_fn(payload)
    decision = resolution.decision

    if decision == "approve":
        carrier = _carrier(
            command=command, severity=severity, band=band,
            decision="approve", would_enforce=True,
        )
        return GateResult(
            outcome=GateOutcome.EXECUTED,
            command=command,
            output=execute(command),
            carriers=[carrier],
        )

    if decision == "edit":
        edited = resolution.edited_command or command
        carrier = _carrier(
            command=edited, severity=severity, band=band,
            decision="edit", would_enforce=True,
        )
        return GateResult(
            outcome=GateOutcome.EXECUTED,
            command=edited,
            output=execute(edited),
            carriers=[carrier],
        )

    # reject / timeout / any unknown decision → fail-closed deny, never executed.
    final_decision = decision if decision in ("reject", "timeout") else "reject"
    carrier = _carrier(
        command=command, severity=severity, band=band,
        decision=final_decision, would_enforce=True,
    )
    return GateResult(
        outcome=GateOutcome.DENIED,
        command=command,
        error_class="gating",
        carriers=[carrier],
    )
