"""Task 3.8b — coach enable-cert replay harness (Phase-3 exit machinery).

Loads a frozen ``coach_goldset_v1`` artifact, replays the (revised) coach judge
over its **test** split to obtain per-item ``answer_leakage`` verdicts, and feeds
those + the frozen gold labels + the manifest to
:func:`services.governance.coach_calibration.evaluate_coach_enable_gates` — then
writes the cert JSON (gate table + verdict) that Task 3.9 pastes into the ledger.

Two layers, so CI stays live-free:

* **Pure core** (``load_goldset`` / ``test_split_gold`` / ``cert_from_labels``) —
  no LLM, no network. Proves ``REFUSE_PROVISIONAL`` on the real provisional
  fixture today and computes ENABLE/REFUSE once a non-provisional freeze exists.
* **Live seam** (``build_live_judges`` / ``replay_test_split`` / ``main``) —
  manual, local-only (``# pragma: no cover - live only``). Renders the frozen
  test split through the real judges. NEVER wired to ``make check`` or CI.

Usage (local, creds in env)::

    .venv/bin/python -m scripts.run_coach_calibration \\
        --goldset tests/fixtures/coach_goldset/coach_goldset_v1.json \\
        --out cache/coach_eval/coach_enable_cert.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.coach_calibration import (
    CoachGateDecision,
    evaluate_coach_enable_gates,
)
from services.governance.coach_goldset_dataset import (
    CoachGoldsetItem,
    CoachGoldsetManifest,
    GoldsetSplit,
)

__all__ = [
    "load_goldset",
    "test_split_gold",
    "cert_from_labels",
    "cert_payload",
    "build_live_judges",
    "replay_test_split",
    "replay_test_split_rows",
    "main",
]


def load_goldset(
    path: Path,
) -> tuple[list[CoachGoldsetItem], CoachGoldsetManifest]:
    """Parse a ``{rows, manifest}`` artifact into typed items + manifest."""
    artifact = json.loads(path.read_text(encoding="utf-8"))
    items = [CoachGoldsetItem.model_validate(r) for r in artifact["rows"]]
    manifest = CoachGoldsetManifest.model_validate(artifact["manifest"])
    return items, manifest


def test_split_gold(items: list[CoachGoldsetItem]) -> dict[str, bool]:
    """Gold ``answer_leakage`` labels for the TEST split ONLY (the cert must not
    read dev-split labels — dev is where the rubric was tuned)."""
    return {i.item_id: i.answer_leakage for i in items if i.split == GoldsetSplit.TEST}


def cert_from_labels(
    *,
    judge_labels: dict[str, bool],
    items: list[CoachGoldsetItem],
    manifest: CoachGoldsetManifest,
) -> CoachGateDecision:
    """Pure cert step: gold from the test split, judge labels restricted to the
    same ids, → ``evaluate_coach_enable_gates``. Fail-closed on a provisional
    manifest happens *inside* the evaluator (no metric read); we do not
    pre-guard, so the single source of the REFUSE_PROVISIONAL rule stays there.
    """
    gold = test_split_gold(items)
    # Restrict judge labels to the gold ids so the confusion sets are 1:1. On the
    # provisional short-circuit ``gold`` may be empty; the evaluator refuses
    # before it ever reads these — passing the full/empty map is harmless.
    judge = {k: judge_labels[k] for k in gold if k in judge_labels}
    return evaluate_coach_enable_gates(
        judge_labels=judge,
        gold_labels=gold,
        manifest=manifest,
    )


def cert_payload(
    decision: CoachGateDecision,
    *,
    goldset_path: str,
    model: str,
    n_test: int,
) -> dict[str, Any]:
    """Serialize the decision into the cert JSON Task 3.9 pastes."""
    # Build the dict field-by-field: ``dataclasses.asdict`` deep-copies the frozen
    # ``mappingproxy`` views on gates/diagnostics, which cannot be pickled.
    d = {
        "verdict": decision.verdict,
        "gates": dict(decision.gates),
        "reasons": list(decision.reasons),
        "diagnostics": dict(decision.diagnostics),
    }
    return {
        "cert_kind": "coach_enable_gates",
        "goldset": goldset_path,
        "model": model,
        "n_test_rows": n_test,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "decision": d,
    }


# ── live seam — manual, local-only (never in CI) ─────────────────────────────


def build_live_judges() -> tuple[Any, Any, str]:  # pragma: no cover - live only
    """Construct the REAL judges (live LLM). Mirrors
    ``scripts.record_coach_judge_validation.build_live_judges`` so the same
    tier/profile wiring drives the cert replay."""
    from scripts.record_coach_judge_validation import build_live_judges as _b

    return _b()


async def replay_test_split(  # pragma: no cover - live only
    items: list[CoachGoldsetItem], *, pedagogy_judge: Any
) -> dict[str, bool]:
    """Render every TEST-split item through the judge → ``answer_leakage`` map.

    A judge that returns ``None`` (abstain) is dropped from ``judge_labels`` — an
    abstention is not a fabricated ``false`` (mirrors the recorder's fail-open
    ban). The dropped id then registers as an undecidable/missing pair in the
    confusion, which is the honest outcome.
    """
    labels: dict[str, bool] = {}
    for item in items:
        if item.split != GoldsetSplit.TEST:
            continue
        verdict = await pedagogy_judge.evaluate(
            learner_utterance=item.learner_utterance,
            coach_reply=item.coach_reply,
            mode=item.mode,
            question=item.question,
        )
        if verdict is None:
            continue
        labels[item.item_id] = bool(getattr(verdict, "answer_leakage", False))
    return labels


async def replay_test_split_rows(
    items: list[CoachGoldsetItem],
    *,
    pedagogy_judge: Any,
    per_call_timeout: float = 60.0,
    dump_path: Path | None = None,
    model: str = "",
) -> list[dict[str, Any]]:
    """Like :func:`replay_test_split`, but keeps the PER-ITEM record for error
    analysis: gold vs judge label, the judge's ``leak_channel``/``rationale``,
    and the reviewer-facing turn context. Abstentions (``None``) are recorded
    with ``judge_leak=None`` so a dropped row is visible, not silently a false.

    Resilience (learned the hard way — a hung provider socket with no timeout
    froze a whole 116-row pass for ~48 min at 0% CPU):

    * ``per_call_timeout`` — each judge call is wrapped in ``asyncio.wait_for``;
      a timeout becomes an **abstention** (``judge_leak=None``), not an infinite
      hang. The pass keeps going.
    * ``dump_path`` — if given, each row is appended to that JSONL **as it
      completes**, so a crash/kill mid-run keeps the rows already done.
    * per-row progress is printed to stderr so a slow pass is visible.

    This feeds ``--dump-labels`` → the open-coding ``cases.json`` for the 3.9
    TNR false-positive triage. It NEVER changes the cert (the cert still reads
    only the boolean map from :func:`replay_test_split`)."""
    test_items = [i for i in items if i.split == GoldsetSplit.TEST]
    total = len(test_items)
    if dump_path is not None:
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text("", encoding="utf-8")  # fresh file for append
    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(test_items, start=1):
        try:
            verdict = await asyncio.wait_for(
                pedagogy_judge.evaluate(
                    learner_utterance=item.learner_utterance,
                    coach_reply=item.coach_reply,
                    mode=item.mode,
                    question=item.question,
                ),
                timeout=per_call_timeout,
            )
        except (TimeoutError, asyncio.TimeoutError):
            print(
                f"  [{idx}/{total}] {item.item_id}: TIMEOUT "
                f"(>{per_call_timeout:.0f}s) → abstain",
                file=sys.stderr,
            )
            verdict = None
        judge_leak = (
            None if verdict is None else bool(getattr(verdict, "answer_leakage", False))
        )
        gold_leak = bool(item.answer_leakage)
        confusion = (
            "abstain"
            if judge_leak is None
            else "tp"
            if (gold_leak and judge_leak)
            else "fp"
            if (not gold_leak and judge_leak)
            else "fn"
            if (gold_leak and not judge_leak)
            else "tn"
        )
        row = {
            "item_id": item.item_id,
            # FR-3 provenance: stamp the judge model into EVERY row so a run's
            # model is recoverable from its artifacts (a mislabeled run — env not
            # switched between replays — is then visible per-row, not only in the
            # cert header). Empty string when unstamped (backward-compatible).
            "judge_model": model,
            "gold_leak": gold_leak,
            "judge_leak": judge_leak,
            "confusion": confusion,
            "judge_leak_channel": (
                None if verdict is None else getattr(verdict, "leak_channel", None)
            ),
            "judge_rationale": (
                None if verdict is None else getattr(verdict, "rationale", None)
            ),
            "mode": item.mode,
            "stratum": item.stratum,
            "provenance": item.provenance,
            "question": item.question,
            "learner_utterance": item.learner_utterance,
            "coach_reply": item.coach_reply,
        }
        rows.append(row)
        if dump_path is not None:
            with dump_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  [{idx}/{total}] {item.item_id}: {confusion}", file=sys.stderr)
    return rows


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - live only
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--goldset",
        type=Path,
        default=REPO_ROOT / "tests/fixtures/coach_goldset/coach_goldset_v1.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "cache/coach_eval/coach_enable_cert.json",
    )
    parser.add_argument(
        "--dump-labels",
        type=Path,
        default=None,
        help=(
            "Optional JSONL: write the per-item gold-vs-judge record "
            "(confusion cell, judge leak_channel/rationale, turn context) for "
            "error analysis of the TNR false positives. Does not affect the cert."
        ),
    )
    parser.add_argument(
        "--per-call-timeout",
        type=float,
        default=60.0,
        help=(
            "Per-judge-call timeout in seconds for the --dump-labels replay. A "
            "call that exceeds it becomes an abstention (never an infinite hang)."
        ),
    )
    args = parser.parse_args(argv)

    items, manifest = load_goldset(args.goldset)

    # On a provisional freeze we need no live call at all — the evaluator refuses
    # before reading a single verdict. Skip the LLM entirely (honest + cheap).
    if manifest.provisional:
        judge_labels: dict[str, bool] = {}
        model = "(none — provisional, no replay)"
    elif args.dump_labels is not None:
        # Rich per-item replay: derive the boolean map the cert needs AND stream
        # the full record to disk row-by-row. One live pass, two consumers. The
        # helper writes ``--dump-labels`` incrementally (crash-safe) and applies
        # a per-call timeout so a hung provider socket can't freeze the pass.
        pedagogy, _grader, model = build_live_judges()
        rows = asyncio.run(
            replay_test_split_rows(
                items,
                pedagogy_judge=pedagogy,
                per_call_timeout=args.per_call_timeout,
                dump_path=args.dump_labels,
                model=model,  # FR-3: stamp the actual judge model into each row
            )
        )
        judge_labels = {
            r["item_id"]: r["judge_leak"] for r in rows if r["judge_leak"] is not None
        }
        n_fp = sum(1 for r in rows if r["confusion"] == "fp")
        n_abstain = sum(1 for r in rows if r["confusion"] == "abstain")
        print(
            f"labels → {args.dump_labels}  rows={len(rows)}  "
            f"false_positives={n_fp}  abstain={n_abstain}"
        )
    else:
        pedagogy, _grader, model = build_live_judges()
        judge_labels = asyncio.run(replay_test_split(items, pedagogy_judge=pedagogy))

    decision = cert_from_labels(
        judge_labels=judge_labels, items=items, manifest=manifest
    )
    n_test = sum(1 for i in items if i.split == GoldsetSplit.TEST)
    payload = cert_payload(
        decision, goldset_path=str(args.goldset), model=model, n_test=n_test
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"cert → {args.out}  verdict={decision.verdict}  "
        f"test_rows={n_test}  gates={dict(decision.gates)}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
