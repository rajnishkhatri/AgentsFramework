"""L2 (Reproducible Reality), Protocol B — the inline carrier gate.

Per ``research/tdd_agentic_systems_prompt.md``:
  - Pattern 11 (Failure Mode Matrix) is the core test, **rejections first**.
  - Pattern 4 (Consumer-Driven Contract): the emitted gap carrier is a valid
    ``TraceEvent`` the ``governance-trace-audit`` skill reads unchanged.
  - AP-2 (no mock addiction): the check is pure over plain strings — zero mocks.
    Only the black-box write in ``record_carrier_gap`` touches I/O, exercised against
    a real on-disk recorder in a tmp dir (no mock).
Deterministic, <30s, every commit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.governance.black_box import BlackBoxRecorder, EventType
from services.governance.carrier_gate import (
    REAL_PHASE_VALUES,
    SPEC_PHASE_VALUES,
    CarrierGap,
    CarrierGateViolation,
    decide_enforcement,
    record_carrier_gap,
    record_enforcement,
    validate_phase_carriers,
)
from services.governance.phase_logger import WorkflowPhase
from trust.governance_carrier_spec import (
    EVT_ERROR_OCCURRED,
    EVT_GOAL_JUDGE,
    EVT_GUARDRAIL_CHECKED,
    EVT_MODEL_SELECTED,
    EVT_STEP_EXECUTED,
    EVT_TASK_STARTED,
    Pillar,
    RunShape,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pattern 11 — Failure Mode Matrix (the §4.2 table, rejections first)
# ─────────────────────────────────────────────────────────────────────────────
# (phase, recorded carriers, tool_failed, run_shape, expected missing pillars)
_MATRIX = [
    # ── rejections first ──
    pytest.param(
        WorkflowPhase.INITIALIZATION,
        set(),
        False,
        RunShape.FROM_STEP_ZERO,
        (Pillar.IDENTITY,),
        id="fresh-init-missing-task-started→Identity",
    ),
    pytest.param(
        WorkflowPhase.MODEL_INVOCATION,
        set(),
        False,
        RunShape.FROM_STEP_ZERO,
        (Pillar.RECORDING,),
        id="model-invocation-no-step-executed→Recording",
    ),
    pytest.param(
        WorkflowPhase.ROUTING,
        set(),
        False,
        RunShape.FROM_STEP_ZERO,
        (Pillar.REASONING,),
        id="routing-no-model-selected→Reasoning",
    ),
    pytest.param(
        WorkflowPhase.TOOL_EXECUTION,
        set(),
        True,
        RunShape.FROM_STEP_ZERO,
        (Pillar.VALIDATION,),
        id="failed-tool-no-error-occurred→Validation (silent failure)",
    ),
    pytest.param(
        WorkflowPhase.INPUT_VALIDATION,
        set(),
        False,
        RunShape.FROM_STEP_ZERO,
        (Pillar.VALIDATION,),
        id="input-validation-no-guardrail-check→Validation",
    ),
    pytest.param(
        WorkflowPhase.OUTPUT_VALIDATION,
        set(),
        False,
        RunShape.FROM_STEP_ZERO,
        (Pillar.VALIDATION,),
        id="output-validation-no-guardrail-check→Validation",
    ),
    pytest.param(
        WorkflowPhase.COMPLETION,
        set(),
        False,
        RunShape.FROM_STEP_ZERO,
        (Pillar.REASONING,),
        id="completion-no-goal-judge→Reasoning (corrupt-success class)",
    ),
    # ── the SKILL.md exemptions (legitimate skips → NO gap) ──
    pytest.param(
        WorkflowPhase.INITIALIZATION,
        set(),
        False,
        RunShape.RESUMED,
        (),
        id="resumed-init-no-task-started→∅ (UNVERIFIABLE, not FAIL)",
    ),
    pytest.param(
        WorkflowPhase.TOOL_EXECUTION,
        set(),
        False,
        RunShape.FROM_STEP_ZERO,
        (),
        id="clean-tool-pass→∅ (quiet)",
    ),
    # ── acceptances (carrier present → NO gap) ──
    pytest.param(
        WorkflowPhase.INITIALIZATION,
        {EVT_TASK_STARTED},
        False,
        RunShape.FROM_STEP_ZERO,
        (),
        id="fresh-init-with-task-started→∅",
    ),
    pytest.param(
        WorkflowPhase.MODEL_INVOCATION,
        {EVT_STEP_EXECUTED},
        False,
        RunShape.FROM_STEP_ZERO,
        (),
        id="model-invocation-with-step-executed→∅",
    ),
    pytest.param(
        WorkflowPhase.COMPLETION,
        {EVT_GOAL_JUDGE},
        False,
        RunShape.FROM_STEP_ZERO,
        (),
        id="completion-with-goal-judge→∅",
    ),
    pytest.param(
        WorkflowPhase.TOOL_EXECUTION,
        {EVT_ERROR_OCCURRED},
        True,
        RunShape.FROM_STEP_ZERO,
        (),
        id="failed-tool-with-error-occurred→∅",
    ),
]


class TestFailureModeMatrix:
    @pytest.mark.parametrize(
        "phase, recorded, tool_failed, run_shape, expected_pillars", _MATRIX
    )
    def test_matrix(self, phase, recorded, tool_failed, run_shape, expected_pillars):
        gap = validate_phase_carriers(
            phase, recorded, tool_failed=tool_failed, run_shape=run_shape
        )
        assert gap.missing_pillars == expected_pillars
        assert gap.ok is (expected_pillars == ())


class TestCheckProperties:
    def test_unknown_phase_string_is_safe(self):
        gap = validate_phase_carriers("not_a_phase", set())
        assert gap.ok and gap.missing == ()

    def test_phase_enum_and_string_agree(self):
        a = validate_phase_carriers(WorkflowPhase.ROUTING, set())
        b = validate_phase_carriers("routing", set())
        assert a.missing_pillars == b.missing_pillars

    def test_extra_unrelated_carriers_do_not_mask_a_gap(self):
        # AP-6 gap-blindness guard: noise carriers must not satisfy a requirement.
        gap = validate_phase_carriers(
            WorkflowPhase.ROUTING, {EVT_GUARDRAIL_CHECKED, EVT_STEP_EXECUTED}
        )
        assert gap.missing_pillars == (Pillar.REASONING,)

    def test_deterministic_over_ten_runs(self):
        for _ in range(10):
            gap = validate_phase_carriers(WorkflowPhase.INITIALIZATION, set())
            assert gap.missing_pillars == (Pillar.IDENTITY,)


class TestSpecDriftGuard:
    """A3 — the trust spec transcribes wire strings it cannot import; assert they
    still equal the real governance enums. If governance renames a value, fail here.
    """

    def test_spec_phase_values_match_real_workflow_phase(self):
        assert SPEC_PHASE_VALUES == REAL_PHASE_VALUES, (
            "trust spec's phase keys drifted from WorkflowPhase — "
            "update trust/governance_carrier_spec.py"
        )

    def test_transcribed_event_values_match_real_event_type(self):
        real = {e.value for e in EventType}
        for v in (
            EVT_TASK_STARTED,
            EVT_STEP_EXECUTED,
            EVT_MODEL_SELECTED,
            EVT_ERROR_OCCURRED,
            EVT_GUARDRAIL_CHECKED,
        ):
            assert v in real, f"spec event value {v!r} is not a real EventType"

    def test_goal_judge_is_not_an_event_type(self):
        # eval.goal_judge is an overlay span, deliberately NOT an EventType.
        assert EVT_GOAL_JUDGE not in {e.value for e in EventType}


class TestConsumerContract:
    """Pattern 4 — the emitted gap carrier is a valid TraceEvent the audit skill
    reads as a Validation-pillar observation. Exercised against a REAL recorder.
    """

    def _read_trace(self, storage: Path, workflow_id: str) -> list[dict]:
        import json

        trace = storage / workflow_id / "trace.jsonl"
        return [
            json.loads(line) for line in trace.read_text().splitlines() if line.strip()
        ]

    def test_gap_emits_alert_carrier(self, tmp_path):
        bb = BlackBoxRecorder(tmp_path)
        gap = validate_phase_carriers(WorkflowPhase.INITIALIZATION, set())
        record_carrier_gap(bb, "wf-1", gap, step=0)

        events = self._read_trace(tmp_path, "wf-1")
        assert len(events) == 1
        ev = events[0]
        assert ev["event_type"] == EventType.GUARDRAIL_CHECKED.value
        assert ev["details"]["source"] == "carrier_gate"
        assert ev["details"]["outcome"] == "alert"
        assert ev["details"]["would_enforce"] is True
        assert ev["details"]["missing_pillars"] == [Pillar.IDENTITY.value]
        assert ev["integrity_hash"], "carrier must join the integrity chain"

    def test_clean_phase_still_records_a_pass_carrier(self, tmp_path):
        bb = BlackBoxRecorder(tmp_path)
        gap = validate_phase_carriers(WorkflowPhase.INITIALIZATION, {EVT_TASK_STARTED})
        record_carrier_gap(bb, "wf-2", gap)

        ev = self._read_trace(tmp_path, "wf-2")[0]
        assert ev["details"]["outcome"] == "pass"
        assert ev["details"]["would_enforce"] is False
        assert ev["details"]["missing_pillars"] == []

    def test_shadow_never_blocks(self):
        # Phase-1 semantics: the check returns a value; it never raises.
        gap = validate_phase_carriers(WorkflowPhase.COMPLETION, set())
        assert isinstance(gap, CarrierGap)  # no exception path


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — enforcement decision matrix (rejections first) + loud-carrier contract
# ─────────────────────────────────────────────────────────────────────────────


def _gap(missing: bool = True) -> CarrierGap:
    """A non-clean gap (missing Identity) or a clean one, for decision tests."""
    return validate_phase_carriers(
        WorkflowPhase.INITIALIZATION,
        set() if missing else {EVT_TASK_STARTED},
    )


class TestEnforcementDecision:
    """``decide_enforcement`` is the pure (gap, mode) → action map. It NEVER
    raises or does I/O — the orchestration caller acts. Rejections (a real gap
    that must be acted on) first, then the legitimate no-ops."""

    def test_gap_in_raise_mode_decides_raise(self):
        d = decide_enforcement(_gap(missing=True), mode="raise")
        assert d.action == "raise"

    def test_gap_in_degrade_mode_decides_degrade(self):
        d = decide_enforcement(_gap(missing=True), mode="degrade")
        assert d.action == "degrade"

    def test_gap_in_off_mode_is_noop(self):
        # Off is shadow parity — a real gap is recorded (Phase 1) but not acted on.
        d = decide_enforcement(_gap(missing=True), mode="off")
        assert d.action == "none"

    def test_clean_phase_is_noop_in_every_mode(self):
        for mode in ("off", "raise", "degrade"):
            d = decide_enforcement(_gap(missing=False), mode=mode)  # type: ignore[arg-type]
            assert d.action == "none", f"clean phase must not enforce in {mode}"

    def test_decision_never_raises(self):
        # The decision is pure data — the raise lives in the orchestration caller.
        for mode in ("off", "raise", "degrade"):
            decide_enforcement(_gap(missing=True), mode=mode)  # type: ignore[arg-type]


class TestCarrierGateViolation:
    def test_violation_names_phase_and_pillars(self):
        gap = _gap(missing=True)
        err = CarrierGateViolation(gap)
        assert err.gap is gap
        assert "initialization" in str(err)
        assert Pillar.IDENTITY.value in str(err)


class TestEnforcementCarrierContract:
    """``record_enforcement`` emits the loud ``carrier_gate_enforce`` carrier so a
    degrade/raise is never silent. Real recorder, no mocks (AP-2)."""

    def _read_trace(self, storage: Path, workflow_id: str) -> list[dict]:
        import json

        trace = storage / workflow_id / "trace.jsonl"
        return [
            json.loads(line) for line in trace.read_text().splitlines() if line.strip()
        ]

    def test_degrade_records_loud_enforced_carrier(self, tmp_path):
        bb = BlackBoxRecorder(tmp_path)
        d = decide_enforcement(_gap(missing=True), mode="degrade")
        record_enforcement(bb, "wf-enf", d, step=0)

        ev = self._read_trace(tmp_path, "wf-enf")[0]
        assert ev["event_type"] == EventType.GUARDRAIL_CHECKED.value
        assert ev["details"]["source"] == "carrier_gate_enforce"
        assert ev["details"]["mode"] == "degrade"
        assert ev["details"]["action"] == "degrade"
        assert ev["details"]["enforced"] is True
        assert ev["details"]["outcome"] == "alert"
        assert ev["details"]["missing_pillars"] == [Pillar.IDENTITY.value]

    def test_raise_decision_also_records_an_enforced_carrier(self, tmp_path):
        # A raise must still leave the trace evidence (the wiring records BEFORE it
        # raises) so dev failures are as auditable as prod degrades.
        bb = BlackBoxRecorder(tmp_path)
        d = decide_enforcement(_gap(missing=True), mode="raise")
        record_enforcement(bb, "wf-raise", d, step=0)
        ev = self._read_trace(tmp_path, "wf-raise")[0]
        assert ev["details"]["action"] == "raise"
        assert ev["details"]["enforced"] is True

    def test_noop_records_nothing(self, tmp_path):
        bb = BlackBoxRecorder(tmp_path)
        d = decide_enforcement(_gap(missing=False), mode="degrade")  # clean → none
        record_enforcement(bb, "wf-clean", d)
        trace = tmp_path / "wf-clean" / "trace.jsonl"
        assert not trace.exists(), (
            "a clean/none decision must record no enforce carrier"
        )
