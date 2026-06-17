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
    record_carrier_gap,
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
    default_spec,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pattern 11 — Failure Mode Matrix (the §4.2 table, rejections first)
# ─────────────────────────────────────────────────────────────────────────────
# (phase, recorded carriers, tool_failed, run_shape, expected missing pillars)
_MATRIX = [
    # ── rejections first ──
    pytest.param(
        WorkflowPhase.INITIALIZATION, set(), False, RunShape.FROM_STEP_ZERO,
        (Pillar.IDENTITY,),
        id="fresh-init-missing-task-started→Identity",
    ),
    pytest.param(
        WorkflowPhase.MODEL_INVOCATION, set(), False, RunShape.FROM_STEP_ZERO,
        (Pillar.RECORDING,),
        id="model-invocation-no-step-executed→Recording",
    ),
    pytest.param(
        WorkflowPhase.ROUTING, set(), False, RunShape.FROM_STEP_ZERO,
        (Pillar.REASONING,),
        id="routing-no-model-selected→Reasoning",
    ),
    pytest.param(
        WorkflowPhase.TOOL_EXECUTION, set(), True, RunShape.FROM_STEP_ZERO,
        (Pillar.VALIDATION,),
        id="failed-tool-no-error-occurred→Validation (silent failure)",
    ),
    pytest.param(
        WorkflowPhase.INPUT_VALIDATION, set(), False, RunShape.FROM_STEP_ZERO,
        (Pillar.VALIDATION,),
        id="input-validation-no-guardrail-check→Validation",
    ),
    pytest.param(
        WorkflowPhase.OUTPUT_VALIDATION, set(), False, RunShape.FROM_STEP_ZERO,
        (Pillar.VALIDATION,),
        id="output-validation-no-guardrail-check→Validation",
    ),
    pytest.param(
        WorkflowPhase.COMPLETION, set(), False, RunShape.FROM_STEP_ZERO,
        (Pillar.REASONING,),
        id="completion-no-goal-judge→Reasoning (corrupt-success class)",
    ),
    # ── the SKILL.md exemptions (legitimate skips → NO gap) ──
    pytest.param(
        WorkflowPhase.INITIALIZATION, set(), False, RunShape.RESUMED,
        (),
        id="resumed-init-no-task-started→∅ (UNVERIFIABLE, not FAIL)",
    ),
    pytest.param(
        WorkflowPhase.TOOL_EXECUTION, set(), False, RunShape.FROM_STEP_ZERO,
        (),
        id="clean-tool-pass→∅ (quiet)",
    ),
    # ── acceptances (carrier present → NO gap) ──
    pytest.param(
        WorkflowPhase.INITIALIZATION, {EVT_TASK_STARTED}, False, RunShape.FROM_STEP_ZERO,
        (),
        id="fresh-init-with-task-started→∅",
    ),
    pytest.param(
        WorkflowPhase.MODEL_INVOCATION, {EVT_STEP_EXECUTED}, False, RunShape.FROM_STEP_ZERO,
        (),
        id="model-invocation-with-step-executed→∅",
    ),
    pytest.param(
        WorkflowPhase.COMPLETION, {EVT_GOAL_JUDGE}, False, RunShape.FROM_STEP_ZERO,
        (),
        id="completion-with-goal-judge→∅",
    ),
    pytest.param(
        WorkflowPhase.TOOL_EXECUTION, {EVT_ERROR_OCCURRED}, True, RunShape.FROM_STEP_ZERO,
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
        return [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]

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
