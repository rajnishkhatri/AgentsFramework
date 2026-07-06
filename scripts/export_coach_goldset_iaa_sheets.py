"""Task 3.7c — export the coach gold-set as BLIND double-label IAA sheets.

Reads the (provisional) ``coach_goldset_v1`` fixture and writes two annotator
sheets + one combined skeleton under ``docs/IAA/coach/goldset/``. Each annotator
sheet carries the item context needed to apply the *options-still-live* leak test
(``learner_utterance``, ``coach_reply``, ``question``, ``mode``) but **not** the
provisional ``answer_leakage`` guess — labeling must be blind (mirrors the
GoalJudge Stage-5 instrument in ``docs/IAA/goalJudge/goldset/``).

The α is scored later by ``scripts/compute_coach_goldset_alpha.py`` off the
combined sheet. This module is pure CSV/JSON — no LLM, no network — so it runs in
``make check``.

Two modes:

* **Mode A (round 1):** export a single frozen goldset fixture (``--goldset``).
* **Mode B (E3 expansion):** join an E1 dev sample + an E2 fresh test batch
  (``--dev-sample`` / ``--test-batch``, jsonl) into the ~210-row blind sheets.
  Dev rows are stamped ``split=dev``/``provenance=synthetic``; the fresh test
  batch is passed through with its ``split=test``/``fresh-authored`` intact.

Usage::

    # Mode A
    .venv/bin/python -m scripts.export_coach_goldset_iaa_sheets \\
        --goldset tests/fixtures/coach_goldset/coach_goldset_v1.json

    # Mode B (E3)
    .venv/bin/python -m scripts.export_coach_goldset_iaa_sheets \\
        --dev-sample cache/coach_eval/coach_dev_sample.jsonl \\
        --test-batch docs/evals/eng-coach/coach_test_batch_v1.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

__all__ = ["build_sheets", "join_dev_and_test", "write_sheet", "main"]

# Context columns shown to annotators (the reply + item to run the leak test on)
# plus provenance columns for traceability. Deliberately EXCLUDES the provisional
# ``answer_leakage`` / ``leak_channel`` guess so the label is blind.
_CONTEXT_COLS = (
    "item_id",
    "split",
    "stratum",
    "mode",
    "provenance",
    "learner_utterance",
    "coach_reply",
    "question",
)


def join_dev_and_test(
    dev_sample: list[dict[str, Any]],
    test_batch: list[dict[str, Any]],
    *,
    existing: list[dict[str, Any]] | None = None,
    dev_id_prefix: str = "D",
) -> list[dict[str, Any]]:
    """Merge the E1 dev sample + E2 fresh test batch into gold-row dicts (E3).

    * ``dev_sample`` — raw corpus turns (``learner_utterance``/``coach_reply``/
      ``mode``, no id/split). Stamped ``split=dev``, ``provenance=synthetic``
      (firewall-legal), and assigned a deterministic ``item_id`` (``D0001``…).
    * ``test_batch`` — E2 rows that ALREADY carry ``split=test`` /
      ``provenance=fresh-authored`` / ``item_id`` / ``stratum``; passed through
      verbatim (the author owns those).
    * ``existing`` — already-labeled round-1 dev rows to carry forward unchanged
      (their ``item_id`` is preserved, not re-blanked).

    Deterministic: dev ids are positional, so a fixed input yields a fixed output.
    The result is the row list ``build_sheets`` consumes. NO ``answer_leakage``
    is set here — labeling stays blind (E4).
    """
    rows: list[dict[str, Any]] = []
    if existing:
        rows.extend(existing)
    for n, r in enumerate(dev_sample, start=1):
        rows.append(
            {
                "item_id": f"{dev_id_prefix}{n:04d}",
                "mode": r.get("mode", ""),
                "question": r.get("question", ""),
                "learner_utterance": r.get("learner_utterance", ""),
                "coach_reply": r.get("coach_reply", ""),
                "stratum": r.get("stratum", ""),
                "split": "dev",
                "provenance": "synthetic",
            }
        )
    rows.extend(test_batch)
    return rows


def build_sheets(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Return ``(annotator1_rows, annotator2_rows, combined_rows)``.

    Annotator rows carry ``_CONTEXT_COLS`` + a single empty ``rN_answer_leakage``
    (+ empty ``rN_note``). The combined skeleton carries both rater columns +
    an empty ``adjudicated_answer_leakage``.
    """
    a1: list[dict[str, str]] = []
    a2: list[dict[str, str]] = []
    combined: list[dict[str, str]] = []
    for r in rows:
        ctx = {c: _stringify(r.get(c)) for c in _CONTEXT_COLS}
        a1.append({**ctx, "r1_answer_leakage": "", "r1_note": ""})
        a2.append({**ctx, "r2_answer_leakage": "", "r2_note": ""})
        combined.append(
            {
                **ctx,
                "r1_answer_leakage": "",
                "r2_answer_leakage": "",
                "adjudicated_answer_leakage": "",
                "note": "",
            }
        )
    return a1, a2, combined


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def write_sheet(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:  # pragma: no cover - the fixture is never empty
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin CLI
    parser = argparse.ArgumentParser(description=__doc__)
    # Mode A (round 1): a single frozen goldset fixture.
    parser.add_argument(
        "--goldset",
        type=Path,
        default=REPO_ROOT / "tests/fixtures/coach_goldset/coach_goldset_v1.json",
    )
    # Mode B (E3 expansion): join an E1 dev sample + E2 fresh test batch (jsonl).
    parser.add_argument("--dev-sample", type=Path, default=None)
    parser.add_argument("--test-batch", type=Path, default=None)
    parser.add_argument(
        "--out-dir", type=Path, default=REPO_ROOT / "docs/IAA/coach/goldset"
    )
    args = parser.parse_args(argv)

    if args.dev_sample or args.test_batch:
        # E3 expansion mode: build the ~210-row superset from the two sources.
        dev = _read_jsonl(args.dev_sample) if args.dev_sample else []
        test = _read_jsonl(args.test_batch) if args.test_batch else []
        rows = join_dev_and_test(dev, test)
    else:
        rows = json.loads(args.goldset.read_text(encoding="utf-8"))["rows"]

    a1, a2, combined = build_sheets(rows)
    write_sheet(args.out_dir / "coach_goldset_annotator1_sheet.csv", a1)
    write_sheet(args.out_dir / "coach_goldset_annotator2_sheet.csv", a2)
    write_sheet(args.out_dir / "coach_goldset_combined_sheet.csv", combined)
    print(
        f"wrote {len(rows)} rows → 2 blind annotator sheets + combined skeleton "
        f"in {args.out_dir}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
