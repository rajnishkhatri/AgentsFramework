"""Coach judge golden-regression gate (Phase-5 task 5.3) — CI-safe, no live LLM.

Recomputes the ADR-0019 certified floor (TNR/TPR/κ) from the COMMITTED recorded-label
runs and fails on a floor breach, a verdict flip across runs, or a malformed/mislabeled
artifact. It grades committed snapshots — it NEVER calls a judge or a provider.

The floor logic is REUSED VERBATIM from the certified evaluator: each run's
``(judge_labels, gold_labels)`` is scored by
``services.governance.coach_calibration.evaluate_coach_enable_gates`` against the frozen
split's manifest. That evaluator already runs the three binding gates (TPR/TNR/κ) with
the inclusive-``≥`` comparison and undecidable-``None``→REFUSE fail-closed semantics
(AP-6), so this module re-derives no metric math. ``flip_rate`` supplies the orthogonal
cross-run zero-flip check.

Layer: ``meta/`` (reads artifacts, produces an evaluation — Invariant #8: imports
``services/`` only, never ``orchestration/``). Mirrors the CI-safe pattern of
``scripts/eval_regression_gate.py``.

Spec: docs/plan/coach-regression-gate.spec.md · Plan/tasks: coach-regression-gate.{plan,tasks}.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from services.governance.coach_calibration import (
    CoachGateDecision,
    evaluate_coach_enable_gates,
    flip_rate,
)
from services.governance.coach_goldset_dataset import CoachGoldsetManifest

_REPO = Path(__file__).resolve().parent.parent

# The three committed recorded-label runs (ADR-0019: glm-5.2-fireworks, zero-flip).
RUN_PATHS: tuple[Path, ...] = tuple(
    _REPO / "docs" / "IAA" / "coach" / "recert" / f"recert_labels_fw_run{n}.jsonl"
    for n in (1, 2, 3)
)
# The frozen split the runs were scored against (its manifest gates provisional/freeze).
SPLIT_PATH: Path = (
    _REPO / "tests" / "fixtures" / "coach_goldset" / "coach_recert_split_v1.json"
)

_CONFUSION_FOR = {
    (True, True): "tp",
    (False, True): "fp",
    (True, False): "fn",
    (False, False): "tn",
}


@dataclass(frozen=True)
class CoachRegressionResult:
    """Outcome of the gate. ``ok`` ⇒ exit 0; ``error`` set ⇒ exit 2; else exit 1."""

    ok: bool
    per_run: list[tuple[str, CoachGateDecision]] = field(default_factory=list)
    flip_count: int | None = None
    violations: list[str] = field(default_factory=list)
    error: str | None = None


def _load_run(path: Path) -> tuple[list[dict] | None, str | None]:
    """Parse + validate one recorded run. Returns ``(rows, None)`` or ``(None, error)``.

    A missing file, zero non-empty lines, an unparseable line, a row missing/non-bool
    ``gold_leak``, or a row whose ``confusion`` disagrees with its ``(gold_leak,
    judge_leak)`` pair is an ERROR — never a silent pass (FR-5, FR-9).

    A row with ``judge_leak == null`` AND ``confusion == "abstain"`` is a VALID judge
    abstention (FR-5b): it is KEPT in ``rows`` (for corpus-identity) but its
    ``judge_leak`` stays ``None``, so metric- and flip-building drop it — exactly as the
    ADR-0019 cert scored run3's ``R-CLEAN-29``.
    """
    if not path.exists():
        return None, f"run file not found: {path}"
    rows: list[dict] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            return None, f"{path.name}:{lineno}: malformed JSON ({exc})"
        gold, judge = obj.get("gold_leak"), obj.get("judge_leak")
        if not isinstance(gold, bool):
            return None, (
                f"{path.name}:{lineno}: gold_leak must be bool (got {gold!r})"
            )
        recorded = obj.get("confusion")
        if judge is None:
            # FR-5b: a declared abstention is valid; anything else non-bool is not.
            if recorded != "abstain":
                return None, (
                    f"{path.name}:{lineno} ({obj.get('item_id')}): judge_leak is null "
                    f"but confusion is {recorded!r}, not 'abstain' (malformed)"
                )
        elif not isinstance(judge, bool):
            return None, (
                f"{path.name}:{lineno}: judge_leak must be bool or a declared "
                f"abstention (got {judge!r})"
            )
        else:
            expected = _CONFUSION_FOR[(gold, judge)]
            if recorded != expected:
                return None, (
                    f"{path.name}:{lineno} ({obj.get('item_id')}): confusion "
                    f"{recorded!r} disagrees with (gold={gold}, judge={judge}) ⇒ "
                    f"{expected!r}"
                )
        rows.append(obj)
    if not rows:
        return None, f"{path.name}: no rows — an empty run is a failure, not a pass"
    return rows, None


def run_coach_regression_gate(
    run_paths: tuple[Path, ...] = RUN_PATHS,
    split_path: Path = SPLIT_PATH,
) -> CoachRegressionResult:
    """Grade the committed runs against the ADR-0019 floor + zero-flip. Pure, no LLM."""
    # 1. Load the frozen split's manifest (the cert-freeze the evaluator gates on).
    try:
        split = json.loads(split_path.read_text())
        manifest = CoachGoldsetManifest(**split["manifest"])
        split_ids = {r["item_id"] for r in split["rows"]}
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return CoachRegressionResult(ok=False, error=f"split load failed: {exc}")

    # 2. Load + validate each run (FR-5, FR-9).
    loaded: list[tuple[str, list[dict]]] = []
    for path in run_paths:
        rows, err = _load_run(path)
        if err is not None:
            return CoachRegressionResult(ok=False, error=err)
        assert rows is not None
        loaded.append((path.name, rows))

    violations: list[str] = []

    # 3. Corpus identity (FR-6): every run must score the frozen split's exact item set.
    for name, rows in loaded:
        run_ids = {r["item_id"] for r in rows}
        if run_ids != split_ids:
            missing = split_ids - run_ids
            extra = run_ids - split_ids
            violations.append(
                f"{name}: corpus mismatch vs frozen split "
                f"(missing={sorted(missing)[:3]}, extra={sorted(extra)[:3]})"
            )

    # 4. Per-run floor via the certified evaluator (FR-1..3, FR-7, FR-10).
    per_run: list[tuple[str, CoachGateDecision]] = []
    for name, rows in loaded:
        # FR-5b: an abstention (judge_leak None) is dropped from the confusion maps —
        # the same items the ADR-0019 cert dropped. gold stays aligned to judge.
        judge = {
            r["item_id"]: r["judge_leak"]
            for r in rows
            if isinstance(r["judge_leak"], bool)
        }
        gold = {
            r["item_id"]: r["gold_leak"]
            for r in rows
            if isinstance(r["judge_leak"], bool)
        }
        decision = evaluate_coach_enable_gates(
            judge_labels=judge, gold_labels=gold, manifest=manifest
        )
        per_run.append((name, decision))
        if decision.verdict != "ENABLE":
            reasons = "; ".join(decision.reasons) or "no reasons"
            violations.append(f"{name}: verdict {decision.verdict} — {reasons}")

    # 5. Zero-flip across the runs (FR-4). Only meaningful when the corpora agree.
    # An abstention (judge_leak None) contributes no verdict, so it is excluded — an
    # item only "flips" among the runs that actually produced a bool verdict for it.
    flip_count: int | None = None
    if all({r["item_id"] for r in rows} == split_ids for _, rows in loaded):
        by_id: dict[str, list[bool]] = {}
        for _, rows in loaded:
            for r in rows:
                if isinstance(r["judge_leak"], bool):
                    by_id.setdefault(r["item_id"], []).append(r["judge_leak"])
        flipped = [iid for iid, verdicts in by_id.items() if len(set(verdicts)) > 1]
        flip_count = len(flipped)
        if flip_count > 0:
            violations.append(f"verdict flip across runs on: {sorted(flipped)[:5]}")
        else:
            # cross-check: flip_rate over the item pairs (first two bool verdicts) is 0.
            pairs = [
                (verdicts[0], verdicts[1])
                for verdicts in by_id.values()
                if len(verdicts) >= 2
            ]
            fr = flip_rate(pairs)
            if fr is not None and fr > 0:
                violations.append(f"flip_rate cross-check nonzero: {fr}")

    return CoachRegressionResult(
        ok=not violations,
        per_run=per_run,
        flip_count=flip_count,
        violations=violations,
        error=None,
    )
