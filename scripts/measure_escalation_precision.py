"""Read-only diagnostic: escalation precision of the hybrid router (Phase 3).

The planning pipeline's hybrid is two decisions measured **separately**
(plan §8 / impl §6.3):

  - **Entry-router accuracy** — does the deterministic ``select_planning_depth``
    pick the right tier up front? Measured by
    ``scripts/diagnose_planning_depth.py`` against live Langfuse traces.
  - **Escalation precision** — when the loop hits a terminal turn, does
    ``components.router.decide_escalation`` re-enter (reflect) only on real
    evidence and never thrash? That is what THIS script measures.

Why a separate offline oracle: the entry diagnostic needs live traces (which
predate Phase 3, and the Langfuse quota is exhausted). Escalation is a pure
scalar predicate (D2 = heuristic-only, no LLM), so it is measured deterministically
against a labelled fixture — CI-safe, zero flake, no network.

Precision and recall are reported because the two failure modes have very
different costs (MAST, plan §9): a **false escalation** wastes a reflexion budget
slot on a clean run (low cost, but it is the thrash risk), while a **missed
escalation** silently ships a confidently-wrong answer (high cost — the exact
failure the §5 primary signal exists to catch). Reporting both keeps the trade-off
legible instead of collapsing it into one accuracy number.

It mutates nothing. It re-runs the tested predicate over each labelled row.

    python scripts/measure_escalation_precision.py
    python scripts/measure_escalation_precision.py --corpus path/to/corpus.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from components.router import decide_escalation

_DEFAULT_CORPUS = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "planning_depth"
    / "escalation_precision_corpus.json"
)


def _load_corpus(path: Path) -> list[dict]:
    rows = json.loads(path.read_text())
    if not isinstance(rows, list):
        raise ValueError(f"corpus must be a JSON array, got {type(rows).__name__}")
    return rows


def score_corpus(rows: list[dict]) -> dict:
    """Run ``decide_escalation`` over the labelled rows; return a metrics dict.

    Returns precision/recall/accuracy plus the confusion-matrix counts and the
    list of mismatched cases (for the operator to inspect).
    """
    tp = fp = tn = fn = 0
    mismatches: list[str] = []

    for row in rows:
        want = bool(row["want_escalate"])
        decision = decide_escalation(
            goal_verdict=row["goal_verdict"],
            unmet_conditions=list(row.get("unmet_conditions") or []),
            prose_kind=row["prose_kind"],
            attempt=int(row["attempt"]),
            max_attempts=int(row["max_attempts"]),
        )
        got = decision == "escalate"

        if got and want:
            tp += 1
        elif got and not want:
            fp += 1
            mismatches.append(f"FALSE-ESCALATE :: {row.get('case', '?')}")
        elif not got and not want:
            tn += 1
        else:  # not got and want
            fn += 1
            mismatches.append(f"MISSED-ESCALATE :: {row.get('case', '?')}")

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    accuracy = (tp + tn) / total if total else 1.0

    return {
        "total": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "accuracy": accuracy,
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=_DEFAULT_CORPUS,
        help="labelled escalation corpus (JSON array)",
    )
    args = parser.parse_args()

    rows = _load_corpus(args.corpus)
    m = score_corpus(rows)

    print(f"escalation-precision oracle :: {args.corpus.name}")
    print(f"  rows           {m['total']}")
    print(f"  precision      {m['precision']:.3f}  (false-escalate / thrash risk)")
    print(f"  recall         {m['recall']:.3f}  (missed escalate / ships wrong answer)")
    print(f"  accuracy       {m['accuracy']:.3f}")
    print(f"  confusion      tp={m['tp']} fp={m['fp']} tn={m['tn']} fn={m['fn']}")
    if m["mismatches"]:
        print("  mismatches:")
        for line in m["mismatches"]:
            print(f"    - {line}")
    print()
    print(
        "entry-router accuracy is the OTHER half of the hybrid — measure it with "
        "scripts/diagnose_planning_depth.py against live traces (plan §8)."
    )
    return 1 if m["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
