"""L1 tests for ``services/governance/eval_graduation.py`` (plan Track B-4).

Pure functions, no I/O, no LLM. Failure/edge paths first (AP-6: undecidable /
no-data is reported explicitly, never silently dropped), then the graduation rule
golden cases, the regression-floor gate, and the Langfuse->goldset projection.
"""

from __future__ import annotations

import pytest

from services.governance.eval_graduation import (
    DEFAULT_MIN_PASS_RATE,
    DEFAULT_MIN_RUNS,
    EvalTier,
    classify_tier,
    eval_record_to_goldset_row,
    graduate,
    regression_floor_violations,
)


# ── classify_tier ───────────────────────────────────────────────────────────────


def test_untagged_row_defaults_to_capability() -> None:
    """Fail-safe: an untagged eval is CAPABILITY, never an accidental regression."""
    assert classify_tier({"case": "x"}) is EvalTier.CAPABILITY


def test_explicit_tiers_parse() -> None:
    assert classify_tier({"tier": "regression"}) is EvalTier.REGRESSION
    assert classify_tier({"tier": "CAPABILITY"}) is EvalTier.CAPABILITY  # case-insens


def test_unknown_tier_raises() -> None:
    with pytest.raises(ValueError, match="unknown tier"):
        classify_tier({"case": "x", "tier": "bogus"})


def test_tier_str_mixin_compares_to_plain_string() -> None:
    assert EvalTier.REGRESSION == "regression"


# ── graduate ────────────────────────────────────────────────────────────────────


def test_graduate_skips_already_regression_rows() -> None:
    rows = [{"case": "a", "tier": "regression"}]
    assert graduate(rows, {"a": (5, 5)}) == []


def test_graduate_no_run_data_reported_not_dropped() -> None:
    [c] = graduate([{"case": "a"}], {})
    assert c.case == "a"
    assert not c.graduates
    assert "insufficient data" in c.reason


def test_graduate_insufficient_runs_holds() -> None:
    [c] = graduate([{"case": "a"}], {"a": (3, 3)}, min_runs=5)
    assert not c.graduates
    assert "only 3 runs" in c.reason


def test_graduate_below_pass_rate_holds() -> None:
    [c] = graduate([{"case": "a"}], {"a": (4, 5)}, min_pass_rate=0.95)
    assert not c.graduates
    assert c.pass_rate == pytest.approx(0.8)


def test_graduate_promotes_stable_capability() -> None:
    [c] = graduate([{"case": "a"}], {"a": (10, 10)})
    assert c.graduates
    assert c.pass_rate == pytest.approx(1.0)
    assert c.runs == 10


def test_graduate_boundary_inclusive_at_threshold() -> None:
    """>= min_pass_rate graduates (inclusive), matching the gate convention."""
    [c] = graduate([{"case": "a"}], {"a": (19, 20)}, min_pass_rate=0.95, min_runs=5)
    assert c.pass_rate == pytest.approx(0.95)
    assert c.graduates


def test_default_thresholds() -> None:
    assert DEFAULT_MIN_PASS_RATE == 0.95
    assert DEFAULT_MIN_RUNS == 5


# ── regression_floor_violations ─────────────────────────────────────────────────


def test_regression_floor_ignores_capability_rows() -> None:
    rows = [{"case": "a", "tier": "capability"}]
    assert regression_floor_violations(rows, {"a": (0, 5)}) == []


def test_regression_perfect_pass_no_violation() -> None:
    rows = [{"case": "a", "tier": "regression"}]
    assert regression_floor_violations(rows, {"a": (5, 5)}) == []


def test_regression_drop_below_floor_is_violation() -> None:
    rows = [{"case": "a", "tier": "regression"}]
    [v] = regression_floor_violations(rows, {"a": (4, 5)})
    assert v.case == "a"
    assert v.pass_rate == pytest.approx(0.8)
    assert v.floor == 1.0


def test_regression_no_run_data_is_silent_gap_violation() -> None:
    """A frozen eval that did not run at all is itself a violation (rate 0.0)."""
    rows = [{"case": "a", "tier": "regression"}]
    [v] = regression_floor_violations(rows, {})
    assert v.pass_rate == 0.0
    assert v.runs == 0


def test_regression_custom_floor() -> None:
    rows = [{"case": "a", "tier": "regression"}]
    assert regression_floor_violations(rows, {"a": (9, 10)}, floor=0.9) == []
    assert regression_floor_violations(rows, {"a": (8, 10)}, floor=0.9)


# ── eval_record_to_goldset_row (Langfuse -> goldset bridge) ──────────────────────


def test_harvested_record_lands_in_capability_tier() -> None:
    """A freshly-harvested real failure must prove itself before regression."""
    row = eval_record_to_goldset_row(
        {"task_id": "t1", "ai_input": {"prompt": "do X"}, "ai_response": "did X"}
    )
    assert row["tier"] == "capability"
    assert row["provenance"] == "langfuse-harvest"


def test_harvest_projects_prompt_and_response_for_load_corpus() -> None:
    row = eval_record_to_goldset_row(
        {
            "task_id": "t1",
            "ai_input": {"prompt": "do X"},
            "ai_response": "did X",
            "model": "claude-haiku-4-5",
            "cost_usd": 0.01,
        }
    )
    # Keys must match the existing corpus row shape so load_corpus accepts it.
    assert row["case"] == "t1"
    assert row["prompt"] == "do X"
    assert row["response_text"] == "did X"
    assert row["model"] == "claude-haiku-4-5"
    assert row["trace_id"] == "t1"


def test_harvest_handles_string_ai_input() -> None:
    row = eval_record_to_goldset_row({"task_id": "t1", "ai_input": "raw prompt"})
    assert row["prompt"] == "raw prompt"


def test_harvest_handles_task_input_key() -> None:
    row = eval_record_to_goldset_row(
        {"task_id": "t1", "ai_input": {"task_input": "via task_input"}}
    )
    assert row["prompt"] == "via task_input"
