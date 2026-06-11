#!/usr/bin/env python3
"""Verify a v0.9 → v1 gold-set cutover at the moment of transition.

Run this **after** the wave-2-extended sheet has been assembled into a
v1 manifest (i.e. ``--provisional`` was *not* passed and the cell-coverage
floors all cleared). It performs the three integrity checks the
:doc:`v0.9 contract <docs/IAA/goalJudge/goldset/goaljudge_stage5_goldset_v0_9_contract>`
prescribes:

  1. **Gate passes against the v1 manifest.** ``gate_goldset_v1_floors``
     returns ``None``; ``provisional`` is ``False``; ``floor_gap_summary``
     is empty.
  2. **Hash changed across the cutover.** The v0.9 hash and v1 hash must
     differ — if they match, the test split is unchanged and no actual
     cutover happened.
  3. **Stable manifest schema.** The v1 manifest has the same key set
     as the v0.9 manifest (no keys added or dropped beyond
     ``provisional`` / ``floor_gap_summary`` which are required on both).

Exits 0 on success, non-zero with a diagnostic on any failure. Pure read
operation; does not mutate any artifact.

Usage:
  python scripts/verify_goldset_v1_cutover.py \\
      --v09 cache/goaljudge_eval/goldset_v0_9_manifest.json \\
      --v1  cache/goaljudge_eval/goldset_v1_manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.governance.goaljudge_goldset_dataset import (
    AssemblyInvariantError,
    gate_goldset_v1_floors,
)


def _load_manifest(path: Path) -> dict[str, object]:
    if not path.exists():
        print(f"manifest not found: {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify v0.9 → v1 gold-set cutover integrity."
    )
    parser.add_argument("--v09", type=Path, required=True,
                        help="Path to the v0.9 (provisional) manifest.")
    parser.add_argument("--v1", type=Path, required=True,
                        help="Path to the v1 (production) manifest.")
    args = parser.parse_args()

    v09 = _load_manifest(args.v09)
    v1 = _load_manifest(args.v1)

    failures: list[str] = []

    # Check 1: gate on v1.
    try:
        gate_goldset_v1_floors(v1)
        print("  [PASS] gate_goldset_v1_floors() passes against v1 manifest")
    except AssemblyInvariantError as exc:
        failures.append(f"v1 manifest fails gate: {exc}")
        print(f"  [FAIL] gate: {exc}")

    # Check 2: hash changed.
    h09 = str(v09.get("test_split_sha256", "")).strip()
    h1 = str(v1.get("test_split_sha256", "")).strip()
    if not h09 or not h1:
        failures.append("one or both manifests have a blank test_split_sha256")
        print("  [FAIL] hash: blank value(s)")
    elif h09 == h1:
        failures.append(
            f"v0.9 and v1 manifests share the same hash {h09!r} — "
            "did the cutover actually add new rows?"
        )
        print(f"  [FAIL] hash unchanged: both manifests have {h09!r}")
    else:
        print(f"  [PASS] hash changed: v0.9={h09[:16]}… v1={h1[:16]}…")

    # Check 3: schema stable.
    keys09 = set(v09.keys())
    keys1 = set(v1.keys())
    if keys09 != keys1:
        added = keys1 - keys09
        removed = keys09 - keys1
        failures.append(
            f"manifest key-set drifted: +{sorted(added)} -{sorted(removed)}"
        )
        print(f"  [FAIL] schema drift: +{sorted(added)} -{sorted(removed)}")
    else:
        print("  [PASS] manifest schema stable across cutover")

    print()
    if failures:
        print(f"CUTOVER VERIFY FAILED ({len(failures)} check(s)):")
        for f in failures:
            print(f"  * {f}")
        return 1
    print("CUTOVER VERIFY PASSED — v1 manifest is healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
