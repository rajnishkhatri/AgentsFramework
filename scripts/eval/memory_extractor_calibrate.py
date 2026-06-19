"""CLI: Stage-6 calibration run for the Phase-2 memory extractor.

Thin shell over ``services.governance.memory_extractor_calibration.score`` (the
trust-anchor math lives there + is unit-tested). This script handles I/O:

  * reads the adjudicated gold CSV (``memory-extract-gold-v1`` schema,
    docs/recipes/memory_extractor/02_goldset_spec.md),
  * gets the extractor's proposals one of three ways:
      --proposals FILE.jsonl   pre-computed proposals (the offline path), OR
      --shadow FILE.jsonl      shadow-carrier export from Langfuse (event=
                               memory.stored, proposed_only=true), OR
      --run-extractor          call the LIVE extractor on each window (needs a
                               provider key; off by default — no LLM in CI),
  * scores against the requested split and prints the verdict + per-gate lines,
  * exits 0 only if EVERY gate passes (so it can gate a flip in a pipeline).

Examples
--------
# Exercise the scorer end-to-end on the bundled synthetic dev set (no key):
python scripts/eval/memory_extractor_calibrate.py \
    --gold docs/recipes/memory_extractor/samples/synthetic_dev_gold.csv \
    --proposals docs/recipes/memory_extractor/samples/synthetic_dev_proposals.jsonl \
    --split dev

# Score the real frozen test split against a Langfuse shadow export:
python scripts/eval/memory_extractor_calibrate.py \
    --gold memory-extract-gold-v1.csv --shadow shadow_export.jsonl --split test
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.governance.memory_enable_policy import (  # noqa: E402
    CERT_SCHEMA,
    REQUIRED_SPLIT,
)
from services.governance.memory_extractor_calibration import (  # noqa: E402
    CalibrationReport,
    GoldRow,
    Proposal,
    score,
)

_TRUE = {"1", "true", "yes", "y", "store"}


def _read_gold(path: Path) -> list[GoldRow]:
    """Parse the gold CSV → GoldRow[]. Example rows (ME-EXAMPLE-*) are skipped."""
    rows: list[GoldRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            item_id = (r.get("item_id") or "").strip()
            if not item_id or item_id.upper().startswith("ME-EXAMPLE"):
                continue
            adjudicated = (r.get("adjudicated_should_store") or "").strip().lower()
            if adjudicated == "":
                # unlabeled row — skip with a stderr note, don't silently pass
                print(f"  (skip {item_id}: no adjudicated_should_store)",
                      file=sys.stderr)
                continue
            gtype = (r.get("adjudicated_type") or "").strip().lower() or None
            rows.append(
                GoldRow(
                    item_id=item_id,
                    split=(r.get("split") or "test").strip().lower(),
                    stratum=(r.get("stratum") or "").strip(),
                    window=(r.get("window") or ""),
                    should_store=adjudicated in _TRUE,
                    gold_type=gtype,
                )
            )
    return rows


def _read_proposals_jsonl(path: Path) -> list[Proposal]:
    """One JSON object per line: {item_id, proposed_store, proposed_type}."""
    out: list[Proposal] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            out.append(
                Proposal(
                    item_id=str(o["item_id"]),
                    proposed_store=bool(o.get("proposed_store", True)),
                    proposed_type=(o.get("proposed_type") or None),
                )
            )
    return out


def _read_shadow_export(path: Path) -> list[Proposal]:
    """Map a Langfuse shadow-carrier export → proposals.

    Each carrier is a MEMORY_STORED event with proposed_only=true and metadata
    {user_id, key, type, salience} — NEVER content. We key proposals by the
    carrier's ``item_id`` field (the gold linkage the export must carry); a
    present carrier == a store proposal of that type.
    """
    out: list[Proposal] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            item_id = o.get("item_id") or o.get("key")
            if item_id is None:
                continue
            out.append(
                Proposal(
                    item_id=str(item_id),
                    proposed_store=True,
                    proposed_type=(o.get("type") or None),
                )
            )
    return out


def _emit_certificate(
    report: CalibrationReport, *, gold_path: Path, out_path: Path
) -> None:
    """Persist the enable-policy certificate the runtime guard re-checks.

    Only the verdict + per-gate pass/fail + counts + the gold file's sha256 —
    never gold content or proposals. The runtime guard
    (services.governance.memory_enable_policy) consumes this; the scorer stays
    the single source of the gate math (this is a pure projection of `report`).
    """
    gold_sha = hashlib.sha256(gold_path.read_bytes()).hexdigest()
    payload = {
        "schema": CERT_SCHEMA,
        "passed": report.passed,
        "split": report.split,
        "total_rows": report.total_rows,
        "gates": [
            {
                "name": g.name,
                "passed": g.passed,
                "value": g.value,
                "threshold": g.threshold,
            }
            for g in report.gates
        ],
        "gold_sha256": gold_sha,
        "scored_at": datetime.now(UTC).isoformat(),
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  wrote enable-policy certificate → {out_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gold", required=True, type=Path,
                   help="adjudicated gold CSV (memory-extract-gold-v1 schema)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--proposals", type=Path,
                     help="pre-computed proposals JSONL {item_id,proposed_store,proposed_type}")
    src.add_argument("--shadow", type=Path,
                     help="Langfuse shadow-carrier export JSONL (memory.stored, proposed_only)")
    src.add_argument("--run-extractor", action="store_true",
                     help="call the LIVE extractor on each window (needs a provider key)")
    p.add_argument("--split", default="test", choices=["dev", "test"],
                   help="which split to score (test is the frozen gate; default)")
    p.add_argument("--emit-certificate", type=Path, default=None, metavar="PATH",
                   help="on a PASSING frozen-test-split run, write the enable-policy "
                        "certificate the runtime guard re-checks "
                        "(MEMORY_AUTOCAPTURE_CERT). Refused on dev or a blocked run.")
    args = p.parse_args(argv)

    gold = _read_gold(args.gold)
    if not gold:
        print("No labeled gold rows found.", file=sys.stderr)
        return 2

    if args.proposals:
        proposals = _read_proposals_jsonl(args.proposals)
    elif args.shadow:
        proposals = _read_shadow_export(args.shadow)
    else:  # --run-extractor
        print(
            "ERROR: --run-extractor requires a configured extractor + provider "
            "key and is intentionally not wired in this offline harness. Produce "
            "proposals via the shadow deploy (DEPLOY_PIECE_C.md §unblocks) and "
            "pass --shadow, or --proposals for an offline run.",
            file=sys.stderr,
        )
        return 3

    report = score(gold, proposals, split=args.split)
    print(report.render())

    if args.emit_certificate is not None:
        # A certificate ENABLES write-back in prod, so we only mint one from a
        # passing run on the FROZEN test split — never dev (AP-4), never blocked.
        if args.split != REQUIRED_SPLIT:
            print(
                f"  (refusing --emit-certificate on split={args.split!r}: only "
                f"the frozen {REQUIRED_SPLIT!r} split clears the gate)",
                file=sys.stderr,
            )
        elif not report.passed:
            print(
                "  (refusing --emit-certificate: run is BLOCKED — no passing "
                "certificate emitted)",
                file=sys.stderr,
            )
        else:
            _emit_certificate(
                report, gold_path=args.gold, out_path=args.emit_certificate
            )

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
