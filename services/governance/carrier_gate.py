"""Carrier gate — the inline governance-trace enforcement check (Phase 1: shadow).

Turns the four-pillar rubric from *audited-after* (the ``governance-trace-audit``
skill, post-hoc) into *checked-during*: given the phase that just ended and the
carriers recorded during it, ``validate_phase_carriers`` returns the **missing
required pillar carriers** by reading the pure ``trust/governance_carrier_spec``
oracle. This realises the arXiv 2603.01548 "binary observability — never a silent
skip" property the trace lacks today.

Layering (AGENTS.md invariant 7, FOUR_LAYER dep table):
  - This is a **horizontal governance service**. It imports only ``trust/`` (the
    spec) and the local ``black_box`` recorder — never ``components`` or
    ``orchestration``.
  - The check is **pure** over plain strings/enums (zero I/O, zero LLM, zero mocks).
  - Governance **emits** a carrier; it does NOT call upward or mutate workflow state
    (AP-4). In Phase 2 the orchestration layer reads the gap carrier and acts.

Phase 1 (this module) **warns only — never blocks** (GG-3): a non-empty gap is
recorded as a ``guardrail_checked`` shadow carrier with ``source: "carrier_gate"``
and ``would_enforce: true`` (mirroring the planning floor's ``would_downgrade``).
Promotion to a real gate (Phase 2) is gated behind shadow calibration.

Drift guard (the trust spec keys on wire strings, not the enums it cannot import):
``EXPECTED_*`` below assert the spec's transcribed values still equal the real
``EventType`` / ``WorkflowPhase`` members; ``tests/services/test_carrier_gate.py``
exercises these so a governance rename fails loudly rather than drifting silently.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from services.governance.black_box import BlackBoxRecorder, EventType, TraceEvent
from services.governance.phase_logger import WorkflowPhase
from trust.governance_carrier_spec import (
    ALL_PHASE_VALUES,
    Pillar,
    PillarCarrierSpec,
    RunShape,
    default_spec,
)

# ── Drift guard: the spec (in trust/) transcribes these wire strings because it may
# not import these enums. If governance renames a value, equality breaks here and the
# service test catches it. Authoritative source = the enums; spec must mirror.
from trust.governance_carrier_spec import (  # noqa: E402  (grouped with the asserts)
    EVT_ERROR_OCCURRED,
    EVT_GUARDRAIL_CHECKED,
    EVT_MODEL_SELECTED,
    EVT_STEP_EXECUTED,
    EVT_TASK_STARTED,
)

# Phase values the spec must mirror exactly (enum-completeness, A3).
SPEC_PHASE_VALUES: frozenset[str] = ALL_PHASE_VALUES
REAL_PHASE_VALUES: frozenset[str] = frozenset(p.value for p in WorkflowPhase)


class MissingCarrier(BaseModel):
    """One pillar carrier that a phase required but did not record."""

    model_config = ConfigDict(frozen=True)

    pillar: Pillar
    event_value: str


class CarrierGap(BaseModel):
    """Result of one phase-boundary check.

    ``missing`` empty ⇒ the phase satisfied the rubric (acceptance). Non-empty ⇒ a
    seam defect: at least one required pillar carrier is absent. ``run_shape`` /
    ``tool_failed`` are echoed so the recorded carrier is self-describing.
    """

    model_config = ConfigDict(frozen=True)

    phase: str
    run_shape: RunShape
    tool_failed: bool
    missing: tuple[MissingCarrier, ...]

    @property
    def ok(self) -> bool:
        return not self.missing

    @property
    def missing_pillars(self) -> tuple[Pillar, ...]:
        return tuple(m.pillar for m in self.missing)


def validate_phase_carriers(
    phase: WorkflowPhase | str,
    recorded_event_values: Iterable[str],
    *,
    tool_failed: bool = False,
    run_shape: RunShape = RunShape.FROM_STEP_ZERO,
    spec: PillarCarrierSpec | None = None,
) -> CarrierGap:
    """Pure check: which required pillar carriers did this phase fail to record?

    ``recorded_event_values`` is the set of EventType/overlay wire strings observed
    during the phase (e.g. ``{"task_started", "model_selected"}``). The spec applies
    the SKILL.md exemptions (resumed-Identity, clean-pass-no-error) before comparing,
    so a legitimate skip never appears as a gap. No I/O, no LLM, deterministic.
    """
    active_spec = spec if spec is not None else default_spec()
    phase_value = phase.value if isinstance(phase, WorkflowPhase) else phase
    recorded = set(recorded_event_values)

    missing = [
        MissingCarrier(pillar=req.pillar, event_value=req.event_value)
        for req in active_spec.required_for(
            phase_value, tool_failed=tool_failed, run_shape=run_shape
        )
        if req.event_value not in recorded
    ]
    return CarrierGap(
        phase=phase_value,
        run_shape=run_shape,
        tool_failed=tool_failed,
        missing=tuple(missing),
    )


def record_carrier_gap(
    black_box: BlackBoxRecorder,
    workflow_id: str,
    gap: CarrierGap,
    *,
    step: int | None = None,
) -> None:
    """Emit the Phase-1 shadow carrier for a checked phase (GG-3 — reuse
    ``guardrail_checked``).

    Always records (even on a clean phase, ``outcome: pass``) so the audit skill sees
    *the check ran* — presence of the check span is itself a Validation-pillar signal.
    A non-empty gap records ``outcome: alert`` + ``would_enforce: true`` (shadow:
    warn, never block). The carrier is a valid ``TraceEvent`` the audit skill reads
    unchanged (consumer-driven contract, Pattern 4).
    """
    black_box.record(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=datetime.now(UTC),
            step=step,
            details={
                "source": "carrier_gate",
                "phase": gap.phase,
                "run_shape": gap.run_shape.value,
                "tool_failed": gap.tool_failed,
                "outcome": "pass" if gap.ok else "alert",
                "missing_pillars": [p.value for p in gap.missing_pillars],
                "missing_carriers": [m.event_value for m in gap.missing],
                # Shadow phase: this is what Phase 2 *would* enforce. Mirrors the
                # planning floor's ``would_downgrade`` calibration flag.
                "would_enforce": not gap.ok,
                "spec_version": (default_spec()).spec_version,
            },
        )
    )


# ── Phase 2: enforcement (flag-gated; governance decides, orchestration acts) ──

EnforcementMode = Literal["off", "raise", "degrade"]


class CarrierGateViolation(Exception):
    """A required pillar carrier was missing and the gate is in ``raise`` mode.

    Raised by the *orchestration* wiring (not here) when ``decide_enforcement``
    returns ``action == "raise"`` — i.e. dev/CI, where a seam defect should fail
    loud at the source. Carries the gap so the failure names the phase + pillars.
    """

    def __init__(self, gap: CarrierGap) -> None:
        self.gap = gap
        pillars = ", ".join(p.value for p in gap.missing_pillars) or "?"
        super().__init__(
            f"carrier-gate violation at phase '{gap.phase}': missing pillar "
            f"carrier(s) [{pillars}] (run_shape={gap.run_shape.value}, "
            f"tool_failed={gap.tool_failed})"
        )


class EnforcementDecision(BaseModel):
    """What the orchestration layer should DO about a gap, under the active mode.

    Pure result — ``decide_enforcement`` never raises or does I/O; it returns this
    and the *caller* acts (AP-4: governance informs, orchestration acts).
      - ``action == "none"``   → do nothing beyond the shadow record (mode off, or
        a clean phase).
      - ``action == "raise"``  → caller raises CarrierGateViolation.
      - ``action == "degrade"``→ caller records the loud degrade carrier
        (``record_enforcement``) + annotates the run, but does NOT block.
    """

    model_config = ConfigDict(frozen=True)

    mode: EnforcementMode
    action: Literal["none", "raise", "degrade"]
    gap: CarrierGap


def decide_enforcement(
    gap: CarrierGap, *, mode: EnforcementMode
) -> EnforcementDecision:
    """Pure mapping (gap, mode) → action. No raise, no I/O — the caller acts.

    A clean phase (``gap.ok``) is always ``none`` regardless of mode — only a real
    missing-carrier gap is ever enforced. ``off`` is always ``none`` (Phase-1
    shadow parity). The dev/prod split is encoded in the mode the caller passes
    (composition derives it from AGENT_ENV), so this stays environment-agnostic.
    """
    if gap.ok or mode == "off":
        return EnforcementDecision(mode=mode, action="none", gap=gap)
    if mode == "raise":
        return EnforcementDecision(mode=mode, action="raise", gap=gap)
    # mode == "degrade"
    return EnforcementDecision(mode=mode, action="degrade", gap=gap)


def record_enforcement(
    black_box: BlackBoxRecorder,
    workflow_id: str,
    decision: EnforcementDecision,
    *,
    step: int | None = None,
) -> None:
    """Emit the loud ENFORCED carrier for a degrade/raise decision (never silent).

    This is the "never a silent skip" guarantee in enforce mode: a separate
    ``guardrail_checked`` carrier with ``source: "carrier_gate_enforce"`` and
    ``enforced: true`` records that the gap was *acted on* (degraded in prod, or
    raised in dev). Distinct ``source`` from the Phase-1 shadow carrier so the
    audit skill / analyzer can tell "the gate fired AND enforced" from "the gate
    merely observed". A clean / off decision records nothing here.
    """
    if decision.action == "none":
        return
    gap = decision.gap
    black_box.record(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            event_type=EventType.GUARDRAIL_CHECKED,
            timestamp=datetime.now(UTC),
            step=step,
            details={
                "source": "carrier_gate_enforce",
                "phase": gap.phase,
                "mode": decision.mode,
                "action": decision.action,
                "outcome": "alert",
                "enforced": True,
                "missing_pillars": [p.value for p in gap.missing_pillars],
                "missing_carriers": [m.event_value for m in gap.missing],
                "spec_version": (default_spec()).spec_version,
            },
        )
    )
