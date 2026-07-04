#!/usr/bin/env python3
"""Phase-3 coding-sample export — posture-filtered coach turns → open-coder JSONL.

The Stage-1 open-coding draw (FR-G2). Runs the posture checker (FR-G1) over a
harvest stream, then:

  1. Computes a deterministic holdout ledger (FR-G2.1–G2.2): a disjoint row set
     reserved for ``coach_goldset_v1`` test-split candidacy. Selection is
     ``SHA-256(task_id, seed)``-bucketed (C10) over ``coding_eligible`` rows
     ONLY — ``partial_context`` rows stay in the coding sample (FR-G1.3: they
     are eligible for open coding, excluded from holdout candidacy), and
     ``confound`` rows are dropped entirely (FR-G2.4).
  2. Exports the coding sample (``coding_eligible`` non-held-out ∪
     ``partial_context``) to open-coder JSONL with the C11 field map:
     ``trace_id←task_id``, ``prompt←learner_utterance``,
     ``final_answer←coach_reply``, plus ``mode``/``question_id``/``provenance``/
     ``stratum``/``meta``.
  3. Emits an honest per-mode count + shortfall report (FR-G2.5) — never
     implying the >= 100/mode coded gate is met from raw harvest counts alone.

Usage:
  python scripts/export_coach_coding_sample.py \\
      --input cache/coach_shadow/coach_corpus.jsonl \\
      --manifest cache/coach_shadow/batch2/manifest.json \\
      --coder-out cache/coach_shadow/batch2_coding_sample.jsonl \\
      --holdout-out cache/coach_shadow/holdout_ledger.json \\
      --provenance synthetic --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from components.schemas import EvalRecord
from meta.coach_corpus_posture import (
    ManifestModeMap,
    PostureClassification,
    check_posture,
    load_manifest_mode_map,
)
from meta.subject_coach_corpus_harvest import (
    GATE_TURNS_PER_MODE,
    parse_harvest_stream,  # noqa: F401 — used in _load_records
)
from meta.subject_coach_judge_sampler import COACH_TARGET, latest_turn_per_task  # noqa: F401 — used in build_coder_rows
from meta.analysis import records_for_target  # noqa: F401 — used in build_coder_rows

__all__ = [
    "DEFAULT_HOLDOUT_FRACTION",
    "ExportReport",
    "HoldoutLedger",
    "build_coder_rows",
    "compute_holdout",
    "main",
    "write_coder_jsonl",
    "write_holdout_ledger",
]

# Hold out ~30% of eligible rows for gold-set test-split candidacy. With the
# batch-2 corpus (~146/mode) this leaves ~100/mode in the coding sample — at
# the FR-G3.1 saturation floor. The fraction is a CLI dial, not a fixed
# constant: the binding constraint is the disjointness + determinism, not the
# exact share.
DEFAULT_HOLDOUT_FRACTION = 0.30

_MODES = ("pre_submit", "post_feedback")


class HoldoutLedger(BaseModel):
    """FR-G2.2 — versioned, seed-reproducible disjoint holdout set."""

    seed: int
    task_ids: list[str]
    created_at: datetime
    fraction: float


class ExportReport(BaseModel):
    """Counts only (AP-6). Two distinct gates, never conflated:

    - ``posture_eligible_per_mode`` + ``shortfall`` + ``gate_met`` — the FR-G2.5
      binding entry gate on posture-eligible rows (the spec's "coding-eligible").
    - ``per_mode`` — the coding-SAMPLE counts (post-holdout), which is what the
      human coder actually sees; feeds the FR-G3.1 saturation floor, NOT the
      FR-G2.5 gate.
    """

    coding_sample_rows: int = 0
    holdout_rows: int = 0
    confound_excluded: int = 0
    partial_context_rows: int = 0
    out_of_batch: int = 0  # manifest-only mode: eligible rows not in the manifest
    per_mode: dict[str, int] = {}  # coding_sample counts per mode (post-holdout)
    posture_eligible_per_mode: dict[str, int] = {}  # FR-G2.5 binding count
    shortfall: dict[str, int] = {}  # on posture_eligible_per_mode
    gate_met: bool = False  # on posture_eligible_per_mode


def compute_holdout(task_ids: list[str], *, seed: int, fraction: float) -> set[str]:
    """Deterministic SHA-256(task_id, seed) bucketing → disjoint holdout set.

    Mirrors the sampler's ``should_sample`` discipline (SHA-256, never ``hash()``)
    so a re-run with the same seed reproduces the split exactly. ``fraction``
    is the share of eligible rows reserved for gold-set test-split candidacy.
    """
    if fraction <= 0.0 or not task_ids:
        return set()
    if fraction >= 1.0:
        return set(task_ids)
    holdout: set[str] = set()
    for tid in task_ids:
        digest = hashlib.sha256(f"{seed}:{tid}".encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:8], "big") / 2**64
        if bucket < fraction:
            holdout.add(tid)
    return holdout


def _coder_row(
    rec: EvalRecord,
    verdict: PostureClassification,
    *,
    manifest: ManifestModeMap | None,
    provenance: str,
) -> dict[str, Any]:
    task_input = str(rec.ai_input.get("task_input", ""))
    reply = (
        rec.ai_response if isinstance(rec.ai_response, str) else str(rec.ai_response)
    )
    mrow = manifest.row_for(task_input) if manifest is not None else None
    return {
        "trace_id": rec.task_id,  # C11: trace_id ← task_id
        "prompt": task_input,  # C11: prompt ← learner_utterance
        "final_answer": reply,  # C11: final_answer ← coach_reply
        "mode": verdict.mode,
        "question_id": (mrow or {}).get("question_id"),
        "provenance": provenance,
        "stratum": (mrow or {}).get("cls"),
        "meta": {
            "step": rec.step,
            "user_id": rec.user_id,
            "model": rec.model,
            "posture_reason": verdict.reason,
        },
    }


def build_coder_rows(
    records: list[EvalRecord],
    classified: list[PostureClassification],
    *,
    manifest: ManifestModeMap | None,
    provenance: Literal["production", "synthetic"],
    seed: int,
    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION,
    manifest_only: bool = False,
) -> tuple[list[dict[str, Any]], set[str], ExportReport]:
    """Posture verdicts -> coding-sample JSONL rows + holdout set + counts report.

    The coding sample = (``coding_eligible`` minus holdout) union
    ``partial_context``.  ``confound`` rows are dropped. Holdout candidacy is drawn from
    ``coding_eligible`` only (``partial_context`` is excluded from holdout per
    FR-G1.3). Per-mode counts + shortfall come from the posture report's
    ``coding_eligible`` buckets (the binding gate is on posture-eligible rows,
    not the post-holdout sample — FR-G2.5).

    ``manifest_only``: when a manifest is provided, treat it as the batch
    boundary — eligible rows whose utterance is NOT in the manifest are reported
    as ``out_of_batch`` (from a different batch sharing the eval log) and not
    shipped. Production harvest passes no manifest, so this never fires there.
    """
    verdict_by_task = {v.task_id: v for v in classified}
    # Build rec_by_task from the SAME collapse posture uses (coach target, latest
    # turn per task). A naive {r.task_id: r for r in records} would overwrite a
    # coach turn with a later non-coach record (goal_judge/guardrail) sharing the
    # task_id — silently emptying task_input in the exported rows.
    coach_turns = latest_turn_per_task(records_for_target(records, COACH_TARGET))
    rec_by_task = {r.task_id: r for r in coach_turns}

    # manifest_only: the manifest defines the batch; restrict holdout candidacy
    # + the coding sample to manifest members so a shared eval log doesn't mix
    # batches. Non-members are counted, never shipped.
    in_manifest: set[str] | None = None
    if manifest_only and manifest is not None:
        in_manifest = {
            tid
            for tid, rec in rec_by_task.items()
            if manifest.row_for(str(rec.ai_input.get("task_input", ""))) is not None
        }

    def _in_batch(task_id: str) -> bool:
        return in_manifest is None or task_id in in_manifest

    eligible_task_ids = [
        v.task_id
        for v in classified
        if v.classification == "coding_eligible" and _in_batch(v.task_id)
    ]
    holdout = compute_holdout(eligible_task_ids, seed=seed, fraction=holdout_fraction)

    rows: list[dict[str, Any]] = []
    per_mode: dict[str, int] = {mode: 0 for mode in _MODES}  # coding sample
    posture_eligible_per_mode: dict[str, int] = {mode: 0 for mode in _MODES}
    confound_excluded = 0
    partial_context_rows = 0
    out_of_batch = 0

    for v in classified:
        rec = rec_by_task.get(v.task_id)
        if rec is None:
            continue
        if v.classification == "confound":
            confound_excluded += 1
            continue
        if not _in_batch(v.task_id):
            out_of_batch += 1
            continue
        # FR-G2.5 binding count: posture-eligible = coding_eligible + partial_context.
        if v.mode in posture_eligible_per_mode:
            posture_eligible_per_mode[v.mode] += 1
        if v.classification == "partial_context":
            rows.append(_coder_row(rec, v, manifest=manifest, provenance=provenance))
            partial_context_rows += 1
            continue
        # coding_eligible — holdout rows are reserved, not exported.
        if v.task_id in holdout:
            continue
        rows.append(_coder_row(rec, v, manifest=manifest, provenance=provenance))
        if v.mode in per_mode:
            per_mode[v.mode] += 1

    # FR-G2.5 shortfall is on posture-eligible rows (the spec's "coding-eligible"),
    # NOT the post-holdout coding sample — raw harvest counts must not imply the
    # coded gate is met from a smaller sample.
    shortfall = {
        mode: max(0, GATE_TURNS_PER_MODE - posture_eligible_per_mode.get(mode, 0))
        for mode in _MODES
    }
    report = ExportReport(
        coding_sample_rows=len(rows),
        holdout_rows=len(holdout),
        confound_excluded=confound_excluded,
        partial_context_rows=partial_context_rows,
        out_of_batch=out_of_batch,
        per_mode=per_mode,
        posture_eligible_per_mode=posture_eligible_per_mode,
        shortfall=shortfall,
        gate_met=all(v == 0 for v in shortfall.values()),
    )
    return rows, holdout, report


def write_holdout_ledger(
    path: Path,
    *,
    task_ids: list[str],
    seed: int,
    fraction: float = DEFAULT_HOLDOUT_FRACTION,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = HoldoutLedger(
        seed=seed,
        task_ids=sorted(task_ids),
        created_at=datetime.now(timezone.utc),
        fraction=fraction,
    )
    path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")


def write_coder_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_manifest(path: Path | None) -> ManifestModeMap | None:
    if path is None or not path.exists():
        return None
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"manifest {path} is not a JSON array")
    return load_manifest_mode_map(rows)


def _load_records(path: Path) -> list[EvalRecord]:
    """Reuse the harvest parser — handles eval-log JSONL, gcloud arrays, and
    logger-envelope lines uniformly (envelope keys ignored by EvalRecord)."""
    records, _skipped = parse_harvest_stream(path.read_text(encoding="utf-8"))
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="harvest corpus JSONL (EvalRecord lines)"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="batch manifest.json (synthetic batches)",
    )
    parser.add_argument(
        "--coder-out", required=True, help="open-coder JSONL output path"
    )
    parser.add_argument(
        "--holdout-out",
        default="cache/coach_shadow/holdout_ledger.json",
        help="holdout ledger output path (FR-G2.2)",
    )
    parser.add_argument(
        "--provenance",
        choices=["production", "synthetic"],
        default="synthetic",
        help="provenance label stamped on every exported row",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--holdout-fraction",
        type=float,
        default=DEFAULT_HOLDOUT_FRACTION,
        help="share of eligible rows reserved for gold-set test-split candidacy",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="when a manifest is provided, treat it as the batch boundary: "
        "eligible rows not in the manifest are reported as out_of_batch and not "
        "shipped (isolates a batch from a shared eval log)",
    )
    args = parser.parse_args(argv)

    src = Path(args.input)
    if not src.exists():
        print(f"input not found: {src}")
        return 1

    records = _load_records(src)
    manifest = _load_manifest(args.manifest)
    classified, posture = check_posture(records, manifest=manifest)

    rows, holdout, report = build_coder_rows(
        records,
        classified,
        manifest=manifest,
        provenance=args.provenance,
        seed=args.seed,
        holdout_fraction=args.holdout_fraction,
        manifest_only=args.manifest_only,
    )

    write_coder_jsonl(Path(args.coder_out), rows)
    write_holdout_ledger(
        Path(args.holdout_out),
        task_ids=sorted(holdout),
        seed=args.seed,
        fraction=args.holdout_fraction,
    )

    print(
        f"posture: {len(classified)} turns -> {posture.coding_eligible} eligible, "
        f"{posture.confound_rows} confound, {posture.partial_context_rows} partial_context"
    )
    print(
        f"coding sample: {report.coding_sample_rows} rows shipped "
        f"({report.partial_context_rows} partial_context) | "
        f"holdout {report.holdout_rows} | confound-excluded {report.confound_excluded}"
        + (f" | out_of_batch {report.out_of_batch}" if args.manifest_only else "")
    )
    print(
        f"per-mode (posture-eligible, FR-G2.5 gate): "
        f"{report.posture_eligible_per_mode} | "
        f"per-mode (coding sample): {report.per_mode} | "
        f"gate ({GATE_TURNS_PER_MODE}/mode): "
        + ("MET" if report.gate_met else f"NOT MET, shortfall {report.shortfall}")
    )
    print(f"coder JSONL -> {args.coder_out}")
    print(f"holdout ledger -> {args.holdout_out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
