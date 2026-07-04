"""Minimal-pair detector (FR-7 / FR-8 / FR-9a).

A minimal pair is two traces with the SAME learner prompt but DIVERGENT
open_codes — proof that a failure was contingent, not forced by the prompt (the
axial "gold"). v1 groups by normalized-EXACT prompt (FR-9a: lowercase, collapse
whitespace, strip surrounding punctuation) — no tunable similarity threshold.

v1 is axis-blind (FR-8): it will surface pairs that diverge only on
environment/judge codes, which are NOISE, not minimal pairs. The output says so
explicitly so a coder does not treat every surfaced pair as gold.

Read-only, stdlib only, framework-agnostic.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

_PUNCT_EDGES = re.compile(r"^[^\w]+|[^\w]+$")
_WS = re.compile(r"\s+")

NOISE_NOTE = (
    "NOTE: v1 is axis-blind. Pairs diverging only on environment-confound or "
    "judge-reliability codes are noise, not minimal pairs — filter by "
    "agent-behavior divergence using the inventory axis column."
)


def normalize_prompt(prompt: str) -> str:
    """FR-9a: lowercase, collapse whitespace, strip surrounding punctuation."""
    s = _WS.sub(" ", prompt.strip().lower())
    return _PUNCT_EDGES.sub("", s)


class _Row:
    __slots__ = ("trace_id", "codes")

    def __init__(self, trace_id: str, codes: list[str]) -> None:
        self.trace_id = trace_id
        self.codes = codes


def _load(coded_path: Path) -> list[tuple[str, _Row]]:
    """Return (normalized_prompt, row) pairs; validate the input contract."""
    out: list[tuple[str, _Row]] = []
    for line in coded_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "trace_id" not in row or "open_codes" not in row:
            raise ValueError(
                "input contract violation: every row needs trace_id + open_codes"
            )
        prompt = row.get("prompt")
        if not prompt:
            continue  # no prompt -> cannot pair; skip (graceful degrade)
        out.append(
            (
                normalize_prompt(prompt),
                _Row(str(row["trace_id"]), list(row["open_codes"] or [])),
            )
        )
    return out


def find_minimal_pairs(coded_path: Path) -> list[dict[str, object]]:
    """Groups sharing a normalized prompt but with divergent code sets."""
    groups: dict[str, list[_Row]] = defaultdict(list)
    for norm, row in _load(coded_path):
        groups[norm].append(row)

    pairs: list[dict[str, object]] = []
    for norm, rows in groups.items():
        if len(rows) < 2:
            continue
        code_sets = {frozenset(r.codes) for r in rows}
        if len(code_sets) < 2:
            continue  # identical coding -> not a divergent pair
        pairs.append(
            {
                "normalized_prompt": norm,
                "members": [
                    {"trace_id": r.trace_id, "open_codes": sorted(r.codes)}
                    for r in rows
                ],
            }
        )
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coded", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.coded.exists():
        print(f"file not found: {args.coded}")
        return 2
    pairs = find_minimal_pairs(args.coded)
    print(json.dumps({"note": NOISE_NOTE, "pairs": pairs}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
