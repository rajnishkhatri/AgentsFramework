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
