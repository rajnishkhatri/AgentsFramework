"""Gate for the planning-stress trace scorer (e2e-stress plan §5.2).

The script ``scripts/analyze_planning_traces.py`` pulls live traces and scores
them; this gate keeps the SCORING logic honest with synthetic events — pure,
deterministic, no LLM (AP5), no network (the source layer is mocked away by
feeding ``score_run`` events directly).

Failure-first (AP6): the headline rows are the precision guards — a false
escalation (thrash) and a missed escalation (ships wrong answer) must surface as
fp/fn, and a depth row that fired the wrong tier must NOT count as a hit.
"""

from __future__ import annotations

from scripts.analyze_planning_traces import gate_failures, score_run


def _step_planned(**details) -> dict:
    return {"event_type": "step_planned", "details": details}


def _task_completed(**details) -> dict:
    return {"event_type": "task_completed", "details": details}


def test_depth_hit_and_miss_are_scored_correctly() -> None:
    rows = [
        {"case": "D-hit", "phase": "depth", "want_depth": "L2"},
        {"case": "D-miss", "phase": "depth", "want_depth": "L2"},
        {"case": "D-gone", "phase": "depth", "want_depth": "L1"},
    ]
    events = {
        "D-hit": [_step_planned(planning_depth="L2", plan_changed=True)],
        # the L0-collapse regression: intended L2, fired L0 -> NOT a hit
        "D-miss": [_step_planned(planning_depth="L0", plan_changed=True)],
        "D-gone": [],  # missing trace
    }
    s = score_run(rows, events)["phases"]["depth"]
    assert s["n"] == 3
    assert s["scored"] == 2  # D-gone excluded from the rate denominator
    assert s["hits"] == 1
    assert s["missing_trace"] == 1
    assert any("MISSING-TRACE" in m for m in s["mismatches"])


def test_replan_recall_and_control_precision() -> None:
    rows = [
        {"case": "R-want", "phase": "replan", "want_replan": True},
        {"case": "R-ctrl", "phase": "replan", "want_replan": False},
        {"case": "R-bad", "phase": "replan", "want_replan": True},  # didn't replan
    ]
    events = {
        "R-want": [
            _step_planned(planning_depth="L1", replanned=True, plan_changed=True)
        ],
        "R-ctrl": [
            _step_planned(planning_depth="L1", replanned=False, plan_changed=True)
        ],
        "R-bad": [
            _step_planned(planning_depth="L1", replanned=False, plan_changed=True)
        ],
    }
    s = score_run(rows, events)["phases"]["replan"]
    assert s["hits"] == 2  # R-want + R-ctrl
    assert any("R-bad" in m for m in s["mismatches"])


def test_reflexion_reentry_and_budget_bound() -> None:
    rows = [
        {"case": "RF-want", "phase": "reflexion", "want_reflexion": True},
        {"case": "RF-ctrl", "phase": "reflexion", "want_reflexion": False},
        {"case": "RF-thrash", "phase": "reflexion", "want_reflexion": True},
    ]
    events = {
        # re-entered twice, bounded by max=2 -> hit
        "RF-want": [
            _step_planned(reflexion_attempt=0, reflexion_critique_chars=40,
                          reflexion_unmet_count=1),
            _step_planned(reflexion_attempt=1, reflexion_critique_chars=37,
                          reflexion_unmet_count=1),
            _task_completed(max_reflexion_attempts=2, escalation_decision="done"),
        ],
        # control: never re-entered -> hit (want_reflexion False)
        "RF-ctrl": [_task_completed(max_reflexion_attempts=2, escalation_decision="done")],
        # thrash: exceeded the ceiling -> NOT bounded -> miss
        "RF-thrash": [
            _step_planned(reflexion_attempt=0, reflexion_critique_chars=40,
                          reflexion_unmet_count=1),
            _step_planned(reflexion_attempt=1, reflexion_critique_chars=40,
                          reflexion_unmet_count=1),
            _step_planned(reflexion_attempt=2, reflexion_critique_chars=40,
                          reflexion_unmet_count=1),
            _task_completed(max_reflexion_attempts=2, escalation_decision="reflect"),
        ],
    }
    s = score_run(rows, events)["phases"]["reflexion"]
    assert s["hits"] == 2  # RF-want + RF-ctrl
    assert any("RF-thrash" in m and "bounded=False" in m for m in s["mismatches"])


def test_escalation_confusion_matrix_counts_both_failure_modes() -> None:
    rows = [
        {"case": "E-tp", "phase": "escalation", "want_escalation": "reflect"},
        {"case": "E-tn", "phase": "escalation", "want_escalation": "done"},
        {"case": "E-fp", "phase": "escalation", "want_escalation": "done"},
        {"case": "E-fn", "phase": "escalation", "want_escalation": "reflect"},
    ]
    events = {
        "E-tp": [_task_completed(escalation_decision="reflect")],
        "E-tn": [_task_completed(escalation_decision="done")],
        "E-fp": [_task_completed(escalation_decision="reflect")],  # false escalate
        "E-fn": [_task_completed(escalation_decision="done")],  # missed escalate
    }
    conf = score_run(rows, events)["escalation_confusion"]
    assert conf["tp"] == 1
    assert conf["tn"] == 1
    assert conf["fp"] == 1  # thrash risk surfaced
    assert conf["fn"] == 1  # ships-wrong-answer risk surfaced
    assert conf["precision"] == 0.5
    assert conf["recall"] == 0.5


def test_gate_flags_thrash_and_missed_escalation() -> None:
    """--gate must fail on either escalation failure mode."""
    rows = [
        {"case": "E-fp", "phase": "escalation", "want_escalation": "done"},
        {"case": "E-fn", "phase": "escalation", "want_escalation": "reflect"},
    ]
    events = {
        "E-fp": [_task_completed(escalation_decision="reflect")],
        "E-fn": [_task_completed(escalation_decision="done")],
    }
    summary = score_run(rows, events)
    fails = gate_failures(summary)
    assert any("false-positive" in f for f in fails)
    assert any("missed-escalation" in f for f in fails)


def test_clean_run_passes_the_gate() -> None:
    rows = [
        {"case": "D", "phase": "depth", "want_depth": "L2"},
        {"case": "R", "phase": "replan", "want_replan": True},
        {"case": "E", "phase": "escalation", "want_escalation": "done"},
    ]
    events = {
        "D": [_step_planned(planning_depth="L2", plan_changed=True)],
        "R": [_step_planned(planning_depth="L1", replanned=True, plan_changed=True)],
        "E": [_task_completed(escalation_decision="done")],
    }
    summary = score_run(rows, events)
    assert gate_failures(summary) == []
