"""Task 3.3d — push coach open-coded cases → Langfuse dataset (FR-G3.1.11–.12).

A coach-specific wrapper over the open-coding skill's exporter: it pins the
dataset name (``coach-phase3-open-coding``) and the coach meta-keys, and keeps
the same idempotent ``uuid5(trace_id)`` item id + item shape so re-running
updates items in place. Defaults to a **dry run**; only ``--write`` touches
Langfuse (FR-G3.1.12), and the real client is imported lazily so the dry-run
path (and its unit tests) need no creds or network.

Usage::

    .venv/bin/python -m scripts.export_coach_open_coding_to_dataset \\
        --coded cache/open_coding/coach-phase3-3.3/coded.jsonl           # dry run
    .venv/bin/python -m scripts.export_coach_open_coding_to_dataset \\
        --coded cache/open_coding/coach-phase3-3.3/coded.jsonl --write
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

__all__ = ["COACH_DATASET", "COACH_META_KEYS", "build_dataset_item", "main"]

COACH_DATASET = "coach-phase3-open-coding"
# Coach cohort keys folded into item metadata (open_codes + memo always included).
COACH_META_KEYS = ("stratum", "mode", "question_id", "provenance")
# Extra keys folded into item input alongside "task" (the prompt).
COACH_ID_KEYS = ("mode", "question_id")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(ln)
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]


def build_dataset_item(row: dict[str, Any]) -> dict[str, Any]:
    """Row → Langfuse dataset item payload (same uuid5 scheme as the skill).

    Idempotent: id = ``uuid5(NAMESPACE_DNS, "opencode-ds:<trace_id>")`` so a
    re-run updates the same item.
    """
    tid = row["trace_id"]
    item_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"opencode-ds:{tid}").hex
    meta: dict[str, Any] = {
        "open_codes": row.get("open_codes", []),
        "memo": row.get("memo", ""),
    }
    for k in COACH_META_KEYS:
        if k in row:
            meta[k] = row[k]
    item_input: dict[str, Any] = {"task": row.get("prompt")}
    for k in COACH_ID_KEYS:
        if k in row:
            item_input[k] = row[k]
    return {
        "id": item_id,
        "input": item_input,
        "expected_output": row.get("final_answer"),
        "metadata": meta,
        "source_trace_id": tid,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coded", required=True, type=Path, help="coded JSONL from the coder"
    )
    parser.add_argument(
        "--write", action="store_true", help="actually push (default: dry run)"
    )
    parser.add_argument(
        "--dataset", default=COACH_DATASET, help="Langfuse dataset name"
    )
    args = parser.parse_args(argv)

    if not args.coded.exists():
        print(f"coded file not found: {args.coded}")
        return 1

    rows = _read_jsonl(args.coded)
    items = [build_dataset_item(r) for r in rows]

    n_uncoded = sum(1 for r in rows if not r.get("open_codes"))
    print(
        f"{len(rows)} cases -> dataset {args.dataset!r}  ({n_uncoded} with NO codes)\n"
    )
    if n_uncoded:
        print(
            f"  ⚠ {n_uncoded} rows have empty open_codes — Enter-commit codes as chips "
            f"in the coder, not the memo. Verify (3.3b) before --write.\n"
        )

    client = None
    if args.write:
        # Lazy import: the real client (creds/network) is only needed on --write.
        from scripts.langfuse_dataset_client import build_real_langfuse_dataset_client

        client = build_real_langfuse_dataset_client()
        client.create_dataset(
            name=args.dataset,
            description=(
                "Coach Phase-3 open-coded case-set (Task 3.3). input=task, "
                "expected_output=coach final answer, metadata=open_codes + memo + "
                "cohort. source_trace_id links to the full run."
            ),
        )

    for row, item in zip(rows, items):
        codes = ", ".join(row.get("open_codes", []))
        action = "WRITE" if args.write else "would write"
        print(f"[{action}] {(row.get('prompt') or '')[:50]!r}  codes=[{codes}]")
        if args.write and client is not None:
            client.create_dataset_item(
                dataset_name=args.dataset,
                id=item["id"],
                input=item["input"],
                expected_output=item["expected_output"],
                metadata=item["metadata"],
                source_trace_id=item["source_trace_id"],
            )

    if args.write:
        print(f"\nwrote {len(items)} items to dataset {args.dataset!r}")
    else:
        print("\nDRY RUN — nothing written. Re-run with --write.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
