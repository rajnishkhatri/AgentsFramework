"""L1 tests for the pass^k + paired-bootstrap additions (plan Track B-2/B-3).

No live LLM. Pure-function math only -- the multi-trial DRIVE (real graph) is
exercised by the opt-in --smoke path, never in CI. Failure/undecidable paths
first (AP-6: an undecidable estimate is None, never a fabricated 0.0), then the
golden hand-computed values, then the NOISE-downgrade contract.
"""

from __future__ import annotations

import json
import uuid
from argparse import Namespace
from pathlib import Path

import pytest

from scripts.model_ab_eval import (
    CONTAMINATED,
    HOLD,
    NOISE,
    PROMOTE,
    _n_choose_k,
    _passk_arm_integrity,
    _passk_provider_contaminated,
    _passk_trials_with_eval_log,
    _run_passk,
    decide_passk_verdict,
    paired_bootstrap_ci,
    pass_hat_k,
)


# ── _n_choose_k ─────────────────────────────────────────────────────────────────


def test_n_choose_k_basic_and_edge() -> None:
    assert _n_choose_k(2, 2) == 1
    assert _n_choose_k(4, 2) == 6
    assert _n_choose_k(2, 3) == 0  # k > n -> no such subset
    assert _n_choose_k(3, 0) == 1
    assert _n_choose_k(-1, 1) == 0


# ── pass_hat_k -- undecidable first ─────────────────────────────────────────────


def test_passk_empty_corpus_is_none() -> None:
    assert pass_hat_k([], trials=3, k=1) is None


def test_passk_k_exceeds_trials_is_none() -> None:
    """No size-k subset of n trials exists -> undecidable, not 0.0."""
    assert pass_hat_k([2, 3], trials=3, k=4) is None


def test_passk_k_below_one_is_none() -> None:
    assert pass_hat_k([2, 3], trials=3, k=0) is None


# ── pass_hat_k -- golden hand-computed values ───────────────────────────────────


def test_passk_pass1_is_mean_pass_rate() -> None:
    """pass^1 == mean per-task pass rate: (1/2 + 2/2)/2 = 0.75."""
    assert pass_hat_k([1, 2], trials=2, k=1) == pytest.approx(0.75)


def test_passk_pass2_unbiased_subset() -> None:
    """pass^2 over [1of2, 2of2]: (C(1,2)/C(2,2) + C(2,2)/C(2,2))/2 = 0.5."""
    assert pass_hat_k([1, 2], trials=2, k=2) == pytest.approx(0.5)


def test_passk_all_pass_is_one() -> None:
    assert pass_hat_k([4, 4, 4], trials=4, k=4) == pytest.approx(1.0)


def test_passk_none_pass_is_zero() -> None:
    """0 successes is a real measurement (denominator exists) -> 0.0, not None."""
    assert pass_hat_k([0, 0], trials=3, k=1) == 0.0


def test_passk_monotonic_decreasing_in_k() -> None:
    """pass^k must not increase as k grows (harder to pass a larger subset)."""
    succ = [3, 2, 4, 1, 4]
    p1 = pass_hat_k(succ, trials=4, k=1)
    p2 = pass_hat_k(succ, trials=4, k=2)
    p4 = pass_hat_k(succ, trials=4, k=4)
    assert p1 is not None and p2 is not None and p4 is not None
    assert p1 >= p2 >= p4


# ── paired_bootstrap_ci ─────────────────────────────────────────────────────────


def test_bootstrap_empty_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        paired_bootstrap_ci([])


def test_bootstrap_single_task_is_point_interval() -> None:
    m, lo, hi = paired_bootstrap_ci([0.2])
    assert m == lo == hi == pytest.approx(0.2)


def test_bootstrap_positive_deltas_exclude_zero() -> None:
    m, lo, hi = paired_bootstrap_ci([0.1, 0.2, 0.15, 0.12, 0.18], seed=0)
    assert m == pytest.approx(0.15)
    assert lo > 0.0  # CI excludes 0 -> a real (non-noise) improvement


def test_bootstrap_zero_centered_deltas_include_zero() -> None:
    m, lo, hi = paired_bootstrap_ci([0.1, -0.1, 0.05, -0.05, 0.0], seed=0)
    assert lo <= 0.0 <= hi  # CI straddles 0 -> noise band


def test_bootstrap_deterministic_for_seed() -> None:
    d = [0.1, -0.2, 0.05, 0.3, -0.1]
    assert paired_bootstrap_ci(d, seed=7) == paired_bootstrap_ci(d, seed=7)


# ── verdict rule (decide_passk_verdict, the B-3 contract, tested DIRECTLY) ───────
#
# decide_passk_verdict is the real rule extracted from _run_passk (review #6): a
# candidate pass^k below baseline is HOLD, BUT if the paired per-task delta CI
# includes 0 it downgrades to NOISE; integrity failure / provider error / an
# undecidable (None) pass^k dominate to CONTAMINATED. We test the actual function,
# not a mirror, so a refactor of the rule can't pass a parallel spec while
# diverging from what _run_passk computes.


def _decide(
    base, cand, *, tolerance=0.0, ci_includes_zero=False, ok=True, contam=False
):
    return decide_passk_verdict(
        base,
        cand,
        tolerance=tolerance,
        ci_includes_zero=ci_includes_zero,
        integrity_ok=ok,
        provider_contaminated=contam,
    )


def test_verdict_regression_with_tight_ci_is_hold() -> None:
    assert _decide(0.9, 0.6, ci_includes_zero=False) == HOLD


def test_verdict_regression_with_straddling_ci_is_noise() -> None:
    assert _decide(0.9, 0.85, ci_includes_zero=True) == NOISE


def test_verdict_improvement_is_promote() -> None:
    assert _decide(0.6, 0.9, ci_includes_zero=False) == PROMOTE


def test_verdict_within_tolerance_is_promote() -> None:
    assert _decide(0.9, 0.88, tolerance=0.05, ci_includes_zero=False) == PROMOTE


def test_verdict_none_passk_is_contaminated() -> None:
    assert _decide(None, 0.9) == CONTAMINATED
    assert _decide(0.9, None) == CONTAMINATED


def test_verdict_integrity_failure_dominates_promote() -> None:
    # Candidate would PROMOTE on score alone, but a failed integrity check wins.
    assert _decide(0.6, 0.9, ok=False) == CONTAMINATED


def test_verdict_provider_contamination_dominates_promote() -> None:
    assert _decide(0.6, 0.9, contam=True) == CONTAMINATED


# ── pass^k guards (Bugbot: integrity / contamination / missing artifacts) ───────


def _write_eval_log(path: Path, case_to_answer: dict[str, tuple[str, int]]) -> None:
    lines = []
    for case, (answer, toks) in case_to_answer.items():
        tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
        lines.append(
            json.dumps(
                {
                    "target": "call_llm",
                    "task_id": tid,
                    "ai_response": answer,
                    "tokens_out": toks,
                    "step": 1,
                }
            )
        )
    path.write_text("\n".join(lines) + "\n")


def test_passk_trials_with_eval_log_counts_snapshots(tmp_path: Path) -> None:
    arm = tmp_path / "baseline"
    (arm / "trial_0").mkdir(parents=True)
    (arm / "trial_2").mkdir(parents=True)
    _write_eval_log(arm / "trial_0" / "evals.log", {"GEN-L1-read-sum-01": ("42", 5)})
    assert _passk_trials_with_eval_log(arm, trials=3) == 1


def test_passk_provider_contaminated_detects_transport_error(tmp_path: Path) -> None:
    arm = tmp_path / "baseline"
    (arm / "trial_0").mkdir(parents=True)
    _write_eval_log(
        arm / "trial_0" / "evals.log",
        {
            "GEN-L1-read-sum-01": (
                "Error: litellm.InternalServerError: Cannot connect",
                0,
            )
        },
    )
    assert _passk_provider_contaminated(arm, trials=1)


def test_passk_provider_contaminated_detects_error_on_non_l1_case(
    tmp_path: Path,
) -> None:
    """Review #2: a transport error on a case NOT in EXPECTED_BY_CASE (an L2/L3
    case) must still contaminate — the guard sweeps every call_llm answer, not
    just the L1 subset the answer scorer grades."""
    arm = tmp_path / "baseline"
    (arm / "trial_0").mkdir(parents=True)
    _write_eval_log(
        arm / "trial_0" / "evals.log",
        # An arbitrary non-GEN-L1 case id => invisible to score_answers, but the
        # log sweep still sees the provider-error marker in its answer.
        {"L2-some-reasoning-case": ("litellm.RateLimitError: overloaded", 0)},
    )
    assert _passk_provider_contaminated(arm, trials=1)


def test_passk_arm_integrity_fails_when_no_recordings(tmp_path: Path) -> None:
    rows = [
        {
            "case": "GEN-L1-read-sum-01",
            "prompt": "sum",
            "trace_id": "t",
            "phase": "depth",
        }
    ]
    arm = tmp_path / "baseline"
    (arm / "trial_0").mkdir(parents=True)
    result = _passk_arm_integrity(rows, arm, trials=1, expected_models={"gpt-4o-mini"})
    assert not result.ok
    assert result.rows_scored == 0


def test_passk_arm_integrity_one_empty_trial_contaminates(tmp_path: Path) -> None:
    """Review #1: a wholly-uninstrumented trial must NOT be masked by a good
    sibling. Before the fix, ``rows_scored = max(...)`` let one trial's nonzero
    count hide an empty trial, yielding ``ok=True`` while pass^k was silently
    depressed. trial_0 has no recordings; with the fix the arm is NOT ok and the
    empty trial is named in the mismatches."""
    rows = [
        {"case": "GEN-L1-read-sum-01", "prompt": "sum", "trace_id": "t", "phase": "d"}
    ]
    arm = tmp_path / "baseline"
    # trial_0: empty (no recordings). trial_1: also no recordings here, but the
    # point is the per-trial empty-trial mismatch fires regardless of siblings.
    (arm / "trial_0").mkdir(parents=True)
    (arm / "trial_1").mkdir(parents=True)
    result = _passk_arm_integrity(rows, arm, trials=2, expected_models={"gpt-4o-mini"})
    assert not result.ok
    assert any("no scored rows" in m for m in result.mismatches)


def test_run_passk_score_only_missing_logs_exits_2(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "case": "GEN-L1-read-sum-01",
                "prompt": "sum",
                "trace_id": "t1",
                "phase": "depth",
            }
        )
        + "\n"
    )
    run_dir = tmp_path / "run"
    (run_dir / "baseline").mkdir(parents=True)
    (run_dir / "candidate").mkdir(parents=True)
    args = Namespace(
        corpus=corpus,
        baseline="gpt-4o-mini",
        candidate="claude-haiku-4-5",
        baseline_set=None,
        candidate_set=None,
        trials=2,
        passk_k=0,
        score_only=True,
        tolerance=0.0,
        gate=False,
    )
    assert _run_passk(args, run_dir, [json.loads(corpus.read_text().strip())]) == 2
