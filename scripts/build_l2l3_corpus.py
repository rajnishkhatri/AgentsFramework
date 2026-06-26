"""Filter the answer corpus to the L2/L3 prose rows for the reasoning-arm sweep.

Source: cache/model_ab_answer/ui_batch.jsonl (19 general rows: 10 L1 + 6 L2 + 3 L3,
produced by convert_model_ab_corpus.py). The L1 rows are already graded
deterministically (scripts/model_ab_answer_score.py + the failure-phrase guard); the
9 L2/L3 rows are prose answers with no trustworthy automated grader and are routed
through the blind-adjudication gold-set process (docs/plans/
model_ab_l2l3_blind_adjudication.plan.md).

This emits just those 9 rows so model_ab_eval.py can drive ONLY them for the
reasoning arms (the harness has --limit but no difficulty filter, so a filtered
corpus file is the clean selector). Row shape is preserved verbatim — the harness
reads case/prompt/trace_id/phase and the answer scorer keys on difficulty.

Idempotent: overwrite each run.
"""

from __future__ import annotations

import json
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = AGENT_ROOT / "cache" / "model_ab_answer" / "ui_batch.jsonl"
DEFAULT_OUT = AGENT_ROOT / "cache" / "model_ab_answer" / "l2l3_batch.jsonl"

L2L3 = {"L2", "L3"}


def filter_l2l3(source: Path = DEFAULT_SOURCE) -> list[dict]:
    """Return the L2/L3 rows (difficulty in {L2,L3}) preserved verbatim."""
    rows: list[dict] = []
    for line in source.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("difficulty") in L2L3:
            rows.append(row)
    return rows


def write_jsonl(rows: list[dict], out: Path = DEFAULT_OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return out


if __name__ == "__main__":
    import sys
    from collections import Counter

    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    rows = filter_l2l3(source)
    write_jsonl(rows, out)
    print(f"filtered {len(rows)} L2/L3 rows -> {out}")
    print("difficulty:", dict(Counter(r["difficulty"] for r in rows)))
    print("cases:", [r["case"] for r in rows])
