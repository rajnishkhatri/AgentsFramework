"""Task 3.3a — build the open-coding ``cases.json`` for the coach gold set.

FR-G3.1.1–.3, .5–.7. A **thin adapter** over
``export_coach_coding_sample.build_coder_rows``: that function already runs the
posture filter (``coding_eligible`` + ``partial_context``, confounds dropped),
joins the batch manifest for full text, and applies the C11 field map
(``trace_id←task_id``, ``prompt←learner_utterance``, ``final_answer←coach_reply``).

Stage-4 note: the coach answer lives in ``logs/evals.log`` EvalRecords, NOT in
``cache/coach_shadow/**/outcomes.jsonl`` (which carries neither ``trace_id`` nor
the reply). So this builder reads EvalRecords and reuses the existing draw — it
does NOT re-derive the join.

Differences from the 3.2 coding-sample export:

- **No holdout is reserved** (``holdout_fraction=0.0``): open coding reads the
  full eligible pool so it can clear the ≥100/mode saturation floor (FR-G3.1.5).
  The gold-set test-split holdout is a *later* concern (Task 3.7), governed by
  its own ledger.
- The output is the coder's ``cases.json`` **array** (not JSONL), ordered so each
  mode is a contiguous block (FR-G3.1.6) — the human codes one mode as one run.
- A mode below ``min_per_mode`` is a **hard error** (``SubFloorError``, FR-G3.1.2),
  never a silently short session.

Usage::

    .venv/bin/python -m scripts.build_coach_open_coding_cases \\
        --input logs/evals.log \\
        --manifest cache/coach_shadow/merged_batch2_2b_manifest.json \\
        --manifest-only \\
        --out cache/open_coding/coach-phase3-3.3/cases.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from components.schemas import EvalRecord
from meta.coach_corpus_posture import ManifestModeMap, check_posture
from scripts.export_coach_coding_sample import (
    _load_manifest,
    _load_records,
    build_coder_rows,
)

__all__ = ["SubFloorError", "build_cases", "write_cases_json", "main"]

_MODES = ("pre_submit", "post_feedback")
DEFAULT_MIN_PER_MODE = 100


class SubFloorError(RuntimeError):
    """A mode has fewer coding-eligible rows than the required floor (FR-G3.1.2)."""


def build_cases(
    records: list[EvalRecord],
    *,
    min_per_mode: int = DEFAULT_MIN_PER_MODE,
    cap_per_mode: int | None = None,
    seed: int = 42,
    manifest: ManifestModeMap | None = None,
    manifest_only: bool = False,
    provenance: str = "synthetic",
) -> list[dict[str, Any]]:
    """EvalRecords → mode-contiguous ``cases.json`` rows, ≥``min_per_mode`` each.

    Reuses ``check_posture`` + ``build_coder_rows`` (no re-derived join). Raises
    ``SubFloorError`` naming every short mode (and its count) before returning a
    sub-floor set — the exact defect the 169-row export sample would introduce.

    ``cap_per_mode`` bounds each mode to at most that many cards (a deterministic
    prefix of the seeded, ``trace_id``-sorted order), to cap the human reading
    load at the ≥100/mode floor. A cap below ``min_per_mode`` is a misconfig.
    """
    if cap_per_mode is not None and cap_per_mode < min_per_mode:
        raise ValueError(
            f"cap_per_mode ({cap_per_mode}) < min_per_mode ({min_per_mode}) — "
            "a cap under the floor would violate FR-G3.1.2"
        )
    classified, _report = check_posture(records, manifest=manifest)
    # holdout_fraction=0.0 → the full eligible pool is available to code.
    rows, _holdout, _export_report = build_coder_rows(
        records,
        classified,
        manifest=manifest,
        provenance=provenance,  # type: ignore[arg-type]
        seed=seed,
        holdout_fraction=0.0,
        manifest_only=manifest_only,
    )

    # FR-G3.1.3: no blank-answer cards. build_coder_rows can emit an eligible row
    # whose reply is empty; a card with no answer is uncodeable → exclude it.
    rows = [r for r in rows if str(r.get("final_answer", "")).strip()]

    by_mode: dict[str, list[dict[str, Any]]] = {m: [] for m in _MODES}
    for r in rows:
        if r.get("mode") in by_mode:
            by_mode[r["mode"]].append(r)

    # FR-G3.1.2: fail closed, naming each short mode + count.
    short = {m: len(by_mode[m]) for m in _MODES if len(by_mode[m]) < min_per_mode}
    if short:
        detail = ", ".join(f"{m}={n}" for m, n in short.items())
        raise SubFloorError(
            f"coding-eligible pool below floor ({min_per_mode}/mode): {detail}"
        )

    # FR-G3.1.7: deterministic order within a mode (sort by trace_id — the
    # upstream draw order is stable but sort makes it explicit + seed-independent
    # for the row SET; seed only affects nothing here since no holdout is drawn).
    # FR-G3.1.6: modes emitted as contiguous blocks.
    cases: list[dict[str, Any]] = []
    for mode in _MODES:
        ordered = sorted(by_mode[mode], key=lambda r: str(r["trace_id"]))
        if cap_per_mode is not None:
            ordered = ordered[:cap_per_mode]  # deterministic prefix of the sort
        cases.extend(ordered)
    return cases


def write_cases_json(path: Path, cases: list[dict[str, Any]]) -> None:
    """Write the coder's ``cases.json`` array (served at ``GET /cases``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="harvest corpus JSONL (EvalRecord lines)"
    )
    parser.add_argument(
        "--manifest", type=Path, default=None, help="batch manifest.json"
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="treat the manifest as the batch boundary (isolate a shared eval log)",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="cases.json output path"
    )
    parser.add_argument("--min-per-mode", type=int, default=DEFAULT_MIN_PER_MODE)
    parser.add_argument(
        "--cap-per-mode",
        type=int,
        default=None,
        help="bound each mode to at most N cards (deterministic prefix; caps reading load)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--provenance", choices=["production", "synthetic"], default="synthetic"
    )
    args = parser.parse_args(argv)

    src = Path(args.input)
    if not src.exists():
        print(f"input not found: {src}")
        return 1

    records = _load_records(src)
    manifest = _load_manifest(args.manifest)
    try:
        cases = build_cases(
            records,
            min_per_mode=args.min_per_mode,
            cap_per_mode=args.cap_per_mode,
            seed=args.seed,
            manifest=manifest,
            manifest_only=args.manifest_only,
            provenance=args.provenance,
        )
    except SubFloorError as exc:
        print(f"SUB-FLOOR: {exc}")
        return 1

    write_cases_json(args.out, cases)
    pre = sum(1 for c in cases if c["mode"] == "pre_submit")
    post = sum(1 for c in cases if c["mode"] == "post_feedback")
    print(f"wrote {len(cases)} cases → {args.out} ({pre} pre / {post} post)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
