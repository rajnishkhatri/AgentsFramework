"""Guards for the Stage-B case report's trace-integrity logic.

The report joins the DOM batch artifact with Langfuse traces by trace_id. The
load-bearing correctness property is **one trace == one run**: if a trace_id is
reused across runs, Langfuse superimposes their carriers and any verdict read
off that trace is a blend of runs (the Stage-B report-integrity defect). These
tests pin the superposition guard so the report fails loud instead of silently
scoring contaminated data. Failure-first per TAP-4.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from report_stage_b_cases import (  # type: ignore  # noqa: E402
    _supervisor_decisions,
    superposition_smell,
)


def _ev(*decisions: str) -> list[dict]:
    """Build a fake event stream with the given supervisor decisions."""
    return [
        {"event_type": "step_planned", "details": {"supervisor_decision": d}}
        for d in decisions
    ]


def _runs(n_run_started: int, *decisions: str) -> list[dict]:
    """Event stream with ``n_run_started`` run.started markers + decisions."""
    ev = [{"event_type": "run_started", "details": {}} for _ in range(n_run_started)]
    ev += list(_ev(*decisions))
    return ev


class TestSuperpositionGuard:
    def test_clean_fanout_only_is_not_contaminated(self) -> None:
        # One run that fanned out (possibly re-entered under reflexion) →
        # all decisions are fan_out. Not contamination.
        assert superposition_smell(_ev("fan_out", "fan_out", "fan_out")) is None

    def test_clean_decline_only_is_not_contaminated(self) -> None:
        assert superposition_smell(_ev("decline")) is None

    def test_no_supervisor_carrier_is_not_contaminated(self) -> None:
        # A non-fanout phase trace (no supervisor at all) must not false-fire.
        assert superposition_smell([{"event_type": "task_completed", "details": {}}]) is None

    def test_mixed_fanout_and_decline_is_contaminated(self) -> None:
        # The real Stage-B trip-research trace: 4 runs superimposed →
        # both fan_out AND decline present on one trace_id.
        smell = superposition_smell(
            _ev("decline", "decline", "fan_out", "decline", "fan_out")
        )
        assert smell is not None
        assert "CONTAMINATED" in smell
        assert "5 decisions" in smell

    def test_decisions_preserve_order(self) -> None:
        assert _supervisor_decisions(_ev("decline", "fan_out")) == ["decline", "fan_out"]


class TestSameDecisionSuperposition:
    """The earlier guard only caught the fan_out+decline mix. Same-prompt reruns
    superimpose under one trace_id with the SAME decision (e.g. fan_out×3) and
    slip through. The reliable, unambiguous signal is >1 ``run.started`` — one
    run emits exactly one. This must NOT false-fire on a single reflexion run
    that re-decides several times (run.started stays 1)."""

    def test_single_run_one_run_started_is_clean(self) -> None:
        assert superposition_smell(_runs(1, "fan_out")) is None

    def test_single_run_reflexion_many_decisions_is_clean(self) -> None:
        # One run, reflexion re-entry → fan_out×3 but run.started == 1. CLEAN.
        assert superposition_smell(_runs(1, "fan_out", "fan_out", "fan_out")) is None

    def test_two_run_started_same_decision_is_contaminated(self) -> None:
        # Same-prompt reruns: fan_out×2 but TWO run.started → superposition.
        smell = superposition_smell(_runs(2, "fan_out", "fan_out"))
        assert smell is not None
        assert "CONTAMINATED" in smell

    def test_mixed_decision_still_caught_when_no_run_markers(self) -> None:
        # Back-compat: traces lacking run.started still caught by decision mix.
        assert superposition_smell(_ev("fan_out", "decline")) is not None
