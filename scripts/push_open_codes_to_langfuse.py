"""Push open-coding results from a coded JSONL onto Langfuse traces (system of record).

Reads the JSONL the HTML coder exports (rows with `trace_id`, `open_codes`, `memo`)
and writes, per trace, a TEXT score carrying the codes + the memo as its comment.
Open codes are emergent free text, so TEXT scores (not a fixed CATEGORICAL config)
are the right surface — they render in the trace's Scores tab. Promote to a
CATEGORICAL score config later, once the codes stabilize into a taxonomy.

Idempotent: score_id is derived deterministically from trace_id + score name, so
re-running UPDATES the same score instead of stacking duplicates.

    # preview only (default — writes nothing):
    python scripts/push_open_codes_to_langfuse.py cache/goaljudge_eval/open_coding/depth_strata_coded.jsonl
    # actually write:
    python scripts/push_open_codes_to_langfuse.py <file>.jsonl --write
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langfuse import Langfuse

SCORE_NAME = "open_code"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", help="coded JSONL exported by the HTML coder")
    ap.add_argument(
        "--write", action="store_true", help="actually write (default: dry run)"
    )
    ap.add_argument(
        "--name", default=SCORE_NAME, help=f"score name (default: {SCORE_NAME})"
    )
    args = ap.parse_args()

    rows = [
        json.loads(line)
        for line in Path(args.jsonl).read_text().splitlines()
        if line.strip()
    ]

    # Only push rows that were actually coded; skip empties so we don't create blank scores.
    coded = [r for r in rows if r.get("open_codes") or r.get("memo", "").strip()]
    print(f"{len(rows)} rows, {len(coded)} carry codes/memo\n")

    bad = [r for r in coded if len(str(r.get("trace_id", ""))) < 32]
    if bad:
        print(
            "WARNING: these rows have short/missing trace_ids and will NOT match Langfuse:"
        )
        for r in bad:
            print(f"  {r.get('trace_id')!r}  {r.get('prompt', '')[:50]}")
        print(
            "  (use the full-id JSONL, e.g. depth_strata_rich.jsonl-derived export)\n"
        )

    client = Langfuse() if args.write else None
    for r in coded:
        tid = str(r.get("trace_id", ""))
        codes = r.get("open_codes") or []
        value = ", ".join(codes) if codes else "(memo only)"
        comment = (r.get("memo") or "").strip() or None
        # deterministic id so re-runs update rather than duplicate
        sid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{tid}:{args.name}").hex
        action = "WRITE" if args.write else "would write"
        print(
            f"[{action}] trace {tid[:12]} <- {args.name}={value!r}"
            + (f"  // {comment}" if comment else "")
        )
        if args.write and len(tid) >= 32:
            client.create_score(
                name=args.name,
                value=value,
                data_type="TEXT",
                trace_id=tid,
                comment=comment,
                score_id=sid,
                metadata={"source": "html-open-coder", "open_codes": codes},
            )

    if args.write:
        client.flush()
        print(f"\nflushed {len(coded)} scores to Langfuse")
    else:
        print("\nDRY RUN — nothing written. Re-run with --write to push.")


if __name__ == "__main__":
    main()
