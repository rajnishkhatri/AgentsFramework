"""Export an open-coded case-set to a Langfuse DATASET.

A dataset gives ONE curated, paginated surface for all coded cases — no
per-observation score scatter, no Hobby-plan annotation-queue cap. Each case
becomes one item carrying the task (input), the agent's final answer
(expected_output), and the open codes + memo + chosen metadata.
`source_trace_id` links the item back to the full trace for drill-down.

Idempotent: each item id is derived from the trace_id (uuid5), so re-running
UPDATES the same item rather than duplicating. Refine codes in the HTML coder,
Save, and re-run with --write to sync.

    python export_coded_to_dataset.py                       # dry run
    python export_coded_to_dataset.py --write \
        --dataset my-coding-session \
        --coded path/to/coded.jsonl \
        --answers path/to/rich.jsonl \
        --meta-keys stratum,want_depth,fired_depth,goal_met

This mirrors the repo convention (RealLangfuseDatasetClient,
agent-compliance-audit / agent-incident-replay). It imports the repo's
scripts.langfuse_dataset_client; run from the repo root with `.venv/bin/python`
(Python 3.13).
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Load repo .env so LANGFUSE_* creds are present (EU host by default).
_repo_root = Path(__file__).resolve()
for _ in range(8):
    if (_repo_root / ".env").exists():
        break
    _repo_root = _repo_root.parent
load_dotenv(_repo_root / ".env")

from scripts.langfuse_dataset_client import build_real_langfuse_dataset_client


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--write", action="store_true", help="actually push (default: dry run)"
    )
    ap.add_argument("--dataset", required=True, help="Langfuse dataset name")
    ap.add_argument(
        "--coded", required=True, type=Path, help="coded JSONL from the coder"
    )
    ap.add_argument(
        "--answers",
        type=Path,
        default=None,
        help="optional JSONL to join final_answer by trace_id (if coded rows lack it)",
    )
    ap.add_argument(
        "--meta-keys",
        default="stratum",
        help="comma list of row keys to copy into item metadata (open_codes + memo always included)",
    )
    ap.add_argument(
        "--id-keys",
        default="",
        help="comma list of extra row keys to fold into the item input alongside 'task'",
    )
    args = ap.parse_args()

    meta_keys = [k.strip() for k in args.meta_keys.split(",") if k.strip()]
    id_keys = [k.strip() for k in args.id_keys.split(",") if k.strip()]

    rows = sorted(
        _read_jsonl(args.coded),
        key=lambda r: r.get("stratum", "") + r.get("prompt", ""),
    )

    # final_answer may live in a separate rich corpus — join by trace_id.
    if args.answers:
        answers = {
            r["trace_id"]: r.get("final_answer") for r in _read_jsonl(args.answers)
        }
        for r in rows:
            r.setdefault("final_answer", answers.get(r["trace_id"]))

    n_uncoded = sum(1 for r in rows if not r.get("open_codes"))
    print(
        f"{len(rows)} cases -> dataset {args.dataset!r}  ({n_uncoded} with NO codes)\n"
    )
    if n_uncoded:
        print(
            f"  ⚠ {n_uncoded} rows have empty open_codes — codes only persist if Enter-committed "
            f"as chips in the coder, not typed into the memo. Verify before --write.\n"
        )

    client = build_real_langfuse_dataset_client() if args.write else None
    if args.write:
        client.create_dataset(
            name=args.dataset,
            description=(
                "Open-coded case-set. input=task, expected_output=agent final answer, "
                "metadata=open codes + memo + cohort. source_trace_id links to the full run."
            ),
        )

    for r in rows:
        item_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"opencode-ds:{r['trace_id']}").hex
        meta = {"open_codes": r.get("open_codes", []), "memo": r.get("memo", "")}
        for k in meta_keys:
            if k in r:
                meta[k] = r[k]
        item_input = {"task": r.get("prompt")}
        for k in id_keys:
            if k in r:
                item_input[k] = r[k]
        codes = ", ".join(r.get("open_codes", []))
        action = "WRITE" if args.write else "would write"
        print(f"[{action}] {(r.get('prompt') or '')[:50]!r}  codes=[{codes}]")
        if args.write:
            client.create_dataset_item(
                dataset_name=args.dataset,
                id=item_id,
                input=item_input,
                expected_output=r.get("final_answer"),
                metadata=meta,
                source_trace_id=r["trace_id"],
            )

    if args.write:
        print(f"\nwrote {len(rows)} items to dataset {args.dataset!r}")
    else:
        print("\nDRY RUN — nothing written. Re-run with --write.")


if __name__ == "__main__":
    main()
