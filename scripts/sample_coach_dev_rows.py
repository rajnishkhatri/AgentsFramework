"""Task E1 — deterministic dev-row sampler over the coach shadow corpus.

Samples ~130 dev-candidate rows from ``cache/coach_shadow/coach_corpus.jsonl``
(all `provenance=synthetic` → dev-split-legal) for the gold-set expansion round.
Two properties matter and both are tested:

* **Deterministic** — a fixed ``seed`` yields a byte-identical row set, so a
  re-run reproduces the exact dev sample (L1 discipline).
* **Bait-biased** — with ``bait_bias=True`` it oversamples utterances carrying a
  leak-*bait* signal (raising the leak prior). It does NOT claim a measured leak
  share: the corpus is unlabeled, so true leakage is only known after E4 human
  labeling (FR-5 amended 2026-07-05, `docs/adr/decisions.md`).

Pure — stdlib only, no LLM, no network — so it runs in ``make check``.

Usage::

    .venv/bin/python -m scripts.sample_coach_dev_rows \\
        --corpus cache/coach_shadow/coach_corpus.jsonl \\
        --n 130 --seed 20260705 --out cache/coach_eval/coach_dev_sample.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

__all__ = [
    "BAIT_SIGNAL",
    "has_bait_signal",
    "dedupe",
    "sample_dev_rows",
    "main",
]

# Learner-utterance phrasings that raise the prior of a leak-bait interaction.
# This is a PROXY (a bait request makes a leak more likely), not a leak label —
# whether the coach_reply actually leaks is decided by E4 labeling.
BAIT_SIGNAL = re.compile(
    r"just tell me|give me the answer|tell me the answer|"
    r"which (choice|one|option) is|tell me which|is it (a|b|c|d)\b|"
    r"what.?s the answer|narrow it down|narrow (it|them) down|"
    r"which concept|should i look up|look up for|definitely wrong|"
    r"which.*(wrong|right)",
    re.IGNORECASE,
)


def has_bait_signal(row: dict[str, Any]) -> bool:
    return bool(BAIT_SIGNAL.search(row.get("learner_utterance", "")))


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (row.get("learner_utterance", ""), row.get("coach_reply", ""))


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop exact ``(learner_utterance, coach_reply)`` duplicates, keeping the
    first occurrence and stable order (so the corpus isn't inflated by copies)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        k = _key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def sample_dev_rows(
    rows: list[dict[str, Any]],
    *,
    n: int,
    seed: int,
    bait_bias: bool = False,
) -> list[dict[str, Any]]:
    """Deterministically sample up to ``n`` deduped rows.

    ``bait_bias`` oversamples bait-signal utterances: bait rows are drawn first
    (shuffled among themselves), then non-bait rows fill the remainder — so the
    bait fraction of the result strictly exceeds the corpus baseline whenever
    both classes are present and ``n`` is between them. Selection within each
    class is seeded, so the result is reproducible.
    """
    pool = dedupe(rows)
    if n >= len(pool):
        # Cap at available rows; still deterministic ordering.
        rng = random.Random(seed)
        out = list(pool)
        rng.shuffle(out)
        return out

    rng = random.Random(seed)
    if not bait_bias:
        out = list(pool)
        rng.shuffle(out)
        return out[:n]

    bait = [r for r in pool if has_bait_signal(r)]
    rest = [r for r in pool if not has_bait_signal(r)]
    rng.shuffle(bait)
    rng.shuffle(rest)
    ordered = bait + rest  # bait first → oversampled when we truncate to n
    return ordered[:n]


def _load(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=REPO_ROOT / "cache/coach_shadow/coach_corpus.jsonl",
    )
    parser.add_argument("--n", type=int, default=130)
    parser.add_argument("--seed", type=int, default=20260705)
    parser.add_argument("--no-bait-bias", action="store_true")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "cache/coach_eval/coach_dev_sample.jsonl",
    )
    args = parser.parse_args(argv)

    rows = _load(args.corpus)
    sample = sample_dev_rows(
        rows, n=args.n, seed=args.seed, bait_bias=not args.no_bait_bias
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for r in sample:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_bait = sum(has_bait_signal(r) for r in sample)
    print(
        f"sampled {len(sample)} dev rows → {args.out} "
        f"({n_bait} bait-signal, {n_bait / len(sample):.0%}) seed={args.seed}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
