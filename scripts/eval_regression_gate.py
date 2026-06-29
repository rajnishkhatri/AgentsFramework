"""Continuously-run regression floor gate (harness v2 plan, item 4.3).

Turns the eval-graduation machinery from latent into practice. The two-tier eval
lifecycle (services/governance/eval_graduation.py) splits evals into CAPABILITY
(expected-to-sometimes-fail probes) and REGRESSION (frozen, formerly-capability
evals the system now passes reliably). This gate runs the REGRESSION tier and
fails when any frozen eval drops below its floor.

Why these rows are graduate-eligible: the GEN-L1 cases carry a deterministic
``EXPECTED`` ground truth (scripts/seed_model_ab_workspace.EXPECTED_BY_CASE) and
are graded by the trustworthy substring scorer (scripts/model_ab_answer_score,
post failure-phrase guard — the plan certifies L1 deterministic grading as
trustworthy). A regression floor on them is meaningful and conservative: a model
that can no longer produce a known integer sum / sorted list / line count SHOULD
trip the alarm.

The regression set + floor live in the COMMITTED corpus
(frontend/e2e/fixtures/model_ab_corpus.json) as a ``tier: "regression"`` field on
each graduated row — not in gitignored cache. This script reads that corpus for
the regression set, scores a run's ``evals.log`` deterministically, and runs
``regression_floor_violations``.

NEVER runs a live LLM — it grades an already-produced ``evals.log`` snapshot.
Off the CI hot path for the *scoring* of a fresh run (which needs a model), but
the gate LOGIC + a recorded-log fixture are CI-safe; see
tests/services/governance/test_eval_regression_gate.py.

Exit codes: 0 = all regression evals at/above floor, 1 = violation(s), 2 = error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from services.governance.eval_graduation import (
    DEFAULT_REGRESSION_FLOOR,
    EvalTier,
    classify_tier,
    regression_floor_violations,
)

AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = AGENT_ROOT / "frontend" / "e2e" / "fixtures" / "model_ab_corpus.json"


def regression_rows(corpus: Sequence[Mapping[str, object]]) -> list[dict]:
    """The subset of corpus rows tagged ``tier: regression``."""
    return [dict(r) for r in corpus if classify_tier(r) is EvalTier.REGRESSION]


def pass_rates_from_eval_log(
    eval_log: Path, cases: Sequence[str]
) -> dict[str, tuple[int, int]]:
    """Score the named cases from a run's eval-log and return case -> (passes, runs).

    Each case is one run here (a single eval-log snapshot), so ``runs`` is 1 and
    ``passes`` is 1 for a correct answer, 0 otherwise. A missing/errored case is a
    miss (0/1) — never silently dropped, matching the scorer's contract.
    """
    # Imported lazily so the module imports without the (heavier) scorer chain
    # when a caller only wants regression_rows / the pure gate logic.
    from scripts.model_ab_answer_score import score_answers

    summary = score_answers(eval_log, list(cases))
    by_case = {s.case: s for s in summary.scores}
    out: dict[str, tuple[int, int]] = {}
    for case in cases:
        score = by_case.get(case)
        out[case] = (1 if (score and score.correct) else 0, 1)
    return out


def run_gate(
    corpus_path: Path,
    eval_log: Path,
    *,
    floor: float = DEFAULT_REGRESSION_FLOOR,
) -> int:
    try:
        corpus = json.loads(corpus_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error reading corpus {corpus_path}: {exc}")
        return 2

    rows = regression_rows(corpus)
    if not rows:
        print("no rows tagged tier:regression in the corpus — nothing to gate")
        return 0

    cases = [str(r.get("case", r.get("id", ""))) for r in rows]
    if not eval_log.exists():
        print(f"error: eval log {eval_log} not found")
        return 2

    pass_rates = pass_rates_from_eval_log(eval_log, cases)
    violations = regression_floor_violations(rows, pass_rates, floor=floor)

    print(f"REGRESSION GATE  ({len(rows)} frozen evals, floor {floor})")
    for case in cases:
        passes, runs = pass_rates[case]
        mark = "ok " if passes >= runs * floor else "MISS"
        print(f"  [{mark}] {case}: {passes}/{runs}")

    if violations:
        print(f"\nREGRESSION GATE: FAIL ({len(violations)} violation(s))")
        for v in violations:
            why = "did not run" if v.runs == 0 else f"rate {v.pass_rate} < {v.floor}"
            print(f"  - {v.case}: {why}")
        return 1

    print("\nREGRESSION GATE: PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regression floor gate (eval 4.3)")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument(
        "--eval-log",
        type=Path,
        required=True,
        help="a run's evals.log to grade the regression tier against",
    )
    parser.add_argument("--floor", type=float, default=DEFAULT_REGRESSION_FLOOR)
    parsed = parser.parse_args(argv)
    return run_gate(parsed.corpus, parsed.eval_log, floor=parsed.floor)


if __name__ == "__main__":
    sys.exit(main())
