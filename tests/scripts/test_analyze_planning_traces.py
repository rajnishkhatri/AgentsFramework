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

from scripts.analyze_planning_traces import (
    _as_bool,
    _as_int,
    _as_list,
    _reflexion_attempts,
    _reflexion_within_budget,
    _replan_count,
    gate_failures,
    score_run,
)


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
        # thrash: a single cycle exceeded its OWN ceiling (attempt 3 > max 2)
        # -> NOT bounded -> miss. (Per-cycle bound: summing carriers across
        # cycles is not thrash; one cycle over its ceiling is.)
        "RF-thrash": [
            _step_planned(reflexion_attempt=0, reflexion_critique_chars=40,
                          reflexion_unmet_count=1),
            _task_completed(reflexion_attempt=3, max_reflexion_attempts=2,
                            escalation_decision="reflect"),
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


def test_langfuse_string_serialized_flags_coerce() -> None:
    """Langfuse serializes JSON bools/ints as STRINGS in observation output.
    The scorer must read "True"/"0" the same as True/0 — a plain `is True`
    silently scored every replan as not-fired (live bug, 2026-06-15)."""
    assert _as_bool("True") is True
    assert _as_bool("False") is False
    assert _as_bool(True) is True
    assert _as_int("2") == 2
    assert _as_int(None, default=0) == 0

    # replanned="True" (string) must count as a replan.
    str_events = [
        {"event_type": "step_planned", "details": {"replanned": "True"}},
        {"event_type": "step_planned", "details": {"replanned": "False"}},
    ]
    assert _replan_count(str_events) == 1

    # terminal reflexion_attempt="1" (string) must register a re-entry even when
    # the per-step critique carrier is absent (Langfuse shape variance).
    refl_events = [
        {"event_type": "task_completed", "details": {"reflexion_attempt": "1"}},
    ]
    assert _reflexion_attempts(refl_events) == 1


def test_langfuse_stringified_list_coerces() -> None:
    """The BlackBox→Langfuse relay stringifies non-allowlisted list values, so the
    carrier-gate ``missing_pillars`` arrives as its Python repr (e.g.
    "['identity']"). ``_as_list`` must parse both the native-list shape (offline
    BlackBox source) and the stringified shape (Langfuse source)."""
    # Native list (offline BlackBox source) passes through.
    assert _as_list(["identity", "reasoning"]) == ["identity", "reasoning"]
    # Stringified list (Langfuse relay) parses back.
    assert _as_list("['identity', 'reasoning']") == ["identity", "reasoning"]
    assert _as_list("['identity']") == ["identity"]
    # Empty / missing → empty list (a clean phase has no missing pillars).
    assert _as_list("[]") == []
    assert _as_list("") == []
    assert _as_list(None) == []
    # A bare scalar or an unparseable string degrades to a single-element list,
    # never raises.
    assert _as_list("identity") == ["identity"]
    assert _as_list("not-a-list-{") == ["not-a-list-{"]


def test_reflexion_budget_is_bounded_per_cycle_not_per_trace() -> None:
    """A checkpoint thread can hold several run cycles, each respecting the
    ceiling. Summing attempts across cycles falsely reports 'unbounded' (live
    bug, 2026-06-15: 4 carriers across cycles vs ceiling 2). The bound must be
    per task.completed."""
    # Two cycles, each hitting attempt=2 with max=2 — BOUNDED (no cycle > 2).
    multi_cycle = [
        _task_completed(reflexion_attempt="2", max_reflexion_attempts="2"),
        _task_completed(reflexion_attempt="2", max_reflexion_attempts="2"),
        _task_completed(reflexion_attempt="0", max_reflexion_attempts="2"),
    ]
    assert _reflexion_within_budget(multi_cycle) is True
    # A single cycle exceeding its own ceiling — UNBOUNDED (real thrash).
    overrun = [_task_completed(reflexion_attempt="3", max_reflexion_attempts="2")]
    assert _reflexion_within_budget(overrun) is False


def _delegation_requested(branch_id: int) -> dict:
    """A per-branch delegation_requested carrier (BlackBox fallback shape)."""
    return {
        "event_type": "tool_called",
        "details": {"delegation_event": "delegation_requested", "branch_id": branch_id},
    }


def _join(*, total: int, completed: int, chars: int = 120) -> dict:
    return _step_planned(
        fanout_join=True,
        branches_total=total,
        branches_completed=completed,
        join_chars=chars,
    )


def test_fanout_false_fanout_is_the_gaia_failure_cell() -> None:
    """THE HEADLINE (failure-first): a near-miss DECLINE row that fanned out
    anyway scores as fp — the GAIA-failure detector. Asserted before tp."""
    rows = [
        {"case": "F-fp", "phase": "fanout", "want_fanout": False},
    ]
    events = {
        # 2 delegation_requested carriers on a want_fanout=False row -> fp.
        "F-fp": [_delegation_requested(1), _delegation_requested(2)],
    }
    conf = score_run(rows, events)["fanout_confusion"]
    assert conf["fp"] == 1, "a fanned-out decline row must score the GAIA fp cell"
    assert conf["tp"] == 0


def test_fanout_partial_survival_counts_for_fault_rows() -> None:
    """A fault row whose join produced a non-empty answer WITH a failed branch
    counts toward partial-survival; a hung/empty join does not."""
    rows = [
        {"case": "Flt-survived", "phase": "fanout", "want_fanout": True,
         "want_survives_partial": True},
        {"case": "Flt-died", "phase": "fanout", "want_fanout": True,
         "want_survives_partial": True},
    ]
    events = {
        # fanned out (>=2 sends) + join with 1 failure + non-empty -> survived.
        "Flt-survived": [
            _delegation_requested(1), _delegation_requested(2), _delegation_requested(3),
            _join(total=3, completed=2),
        ],
        # fanned out but the join is empty (a hang/crash) -> did NOT survive.
        "Flt-died": [
            _delegation_requested(1), _delegation_requested(2),
            _join(total=2, completed=0, chars=0),
        ],
    }
    summary = score_run(rows, events)
    assert summary["partial_survival"]["eligible"] == 2
    assert summary["partial_survival"]["survived"] == 1
    assert summary["partial_survival_rate"] == 0.5


def test_fanout_correct_fanout_scores_tp_and_decline_scores_tn() -> None:
    """The acceptance rows: a correct fan-out is tp, a correct decline is tn."""
    rows = [
        {"case": "F-tp", "phase": "fanout", "want_fanout": True},
        {"case": "F-tn", "phase": "fanout", "want_fanout": False},
        {"case": "F-fn", "phase": "fanout", "want_fanout": True},  # missed (cheap)
    ]
    events = {
        "F-tp": [_delegation_requested(1), _delegation_requested(2),
                 _join(total=2, completed=2)],
        "F-tn": [_step_planned(supervisor_decision="decline",
                               supervisor_reason="sequential-dependent")],
        "F-fn": [_step_planned(supervisor_decision="decline",
                               supervisor_reason="single-step")],
    }
    conf = score_run(rows, events)["fanout_confusion"]
    assert conf["tp"] == 1
    assert conf["tn"] == 1
    assert conf["fn"] == 1  # reported, not gated


def test_fanout_gate_fails_on_false_fanout_but_not_on_missed() -> None:
    """--gate fails on a GAIA fp (precision < 0.9) but a missed fan-out (recall)
    alone does NOT fail the gate (it is the cheap error, plan §3.5a)."""
    # One fp among one tp -> precision 0.5 < 0.9 -> gate fails.
    fp_rows = [
        {"case": "F-tp", "phase": "fanout", "want_fanout": True},
        {"case": "F-fp", "phase": "fanout", "want_fanout": False},
    ]
    fp_events = {
        "F-tp": [_delegation_requested(1), _delegation_requested(2)],
        "F-fp": [_delegation_requested(1), _delegation_requested(2)],
    }
    fails = gate_failures(score_run(fp_rows, fp_events))
    assert any("fanout precision" in f for f in fails)

    # A pure missed-fan-out batch (recall low, precision perfect) -> NO gate fail.
    fn_rows = [{"case": "F-fn", "phase": "fanout", "want_fanout": True}]
    fn_events = {"F-fn": [_step_planned(supervisor_decision="decline",
                                        supervisor_reason="single-step")]}
    assert gate_failures(score_run(fn_rows, fn_events)) == []


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
