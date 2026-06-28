"""Export the 11 open-coded planning-depth cases to a Langfuse DATASET.

A dataset gives ONE curated surface for all cases (no per-observation score
scatter, no Hobby-plan queue cap): each case is one item carrying the task
(input), the agent's final answer (expected_output), and the open codes +
role/support + depth metadata. `source_trace_id` links each item back to the
full trace for trajectory drill-down.

Mirrors the repo's existing dataset convention (RealLangfuseDatasetClient,
agent-compliance-audit / agent-incident-replay).

Idempotent: dataset item id is derived from the trace_id, so re-running
updates the same item instead of duplicating.

    python scripts/export_depth_cases_to_dataset.py            # dry run
    python scripts/export_depth_cases_to_dataset.py --write
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from scripts.langfuse_dataset_client import build_real_langfuse_dataset_client

DATASET = "planning-depth-open-coding"
CODED = Path("cache/goaljudge_eval/open_coding/depth_strata_coded.jsonl")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--write", action="store_true", help="actually create (default: dry run)"
    )
    ap.add_argument("--dataset", default=DATASET)
    args = ap.parse_args()

    rows = sorted(
        (json.loads(l) for l in CODED.read_text().splitlines() if l.strip()),
        key=lambda r: (r["want_depth"], r["prompt"]),
    )
    # final_answer lives in the rich corpus, not the coded file — join by trace_id.
    rich_path = Path("cache/goaljudge_eval/depth_strata_rich.jsonl")
    answers = {
        json.loads(l)["trace_id"]: json.loads(l).get("final_answer")
        for l in rich_path.read_text().splitlines()
        if l.strip()
    }
    for r in rows:
        r["final_answer"] = answers.get(r["trace_id"])
    print(f"{len(rows)} cases -> dataset {args.dataset!r}\n")

    client = build_real_langfuse_dataset_client() if args.write else None
    if args.write:
        client.create_dataset(
            name=args.dataset,
            description=(
                "GJ-DEPTH planning-depth strata, open-coded. input=task, "
                "expected_output=agent final answer, metadata=open codes + depth. "
                "source_trace_id links to the full run."
            ),
        )

    for r in rows:
        item_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"depth-ds:{r['trace_id']}").hex
        meta = {
            "want_depth": r["want_depth"],
            "fired_depth": r["fired_depth"],
            "depth_miss": r["want_depth"] != r["fired_depth"],
            "stratum": r["stratum"],
            "open_codes": r["open_codes"],
            "code_detail": r.get("code_detail", []),
            "goal_met": r.get("goal_met"),
            "partial_fraction": r.get("partial_fraction"),
        }
        codes = ", ".join(r["open_codes"])
        action = "WRITE" if args.write else "would write"
        print(
            f"[{action}] {r['want_depth']}/{r['fired_depth']} {r['prompt'][:46]!r}  codes=[{codes}]"
        )
        if args.write:
            client.create_dataset_item(
                dataset_name=args.dataset,
                id=item_id,
                input={"task": r["prompt"], "want_depth": r["want_depth"]},
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
