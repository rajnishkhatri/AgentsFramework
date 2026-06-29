"""Append the Wave-1 growth L2/L3 cases (16–24) to the model-A/B answer corpus.

Items 1.3/1.4 of docs/plan/harness_adoption_v2_practical_adoption.plan.md grow the
L2/L3 seed toward >=100 rows. The 9 original cases (07–15) gave 54 cells (52 after
the truncation exclusion, ADR-0003); 9 more cases x 6 arms = 108 cells, comfortably
>=100. Their fixtures + ground truth already live in seed_model_ab_l2l3_workspace.py
(the single source of truth); this module emits the matching corpus ROWS (prompts).

Row shape mirrors the existing ui_batch.jsonl rows exactly:
  case, gj_id (GJ-ABGENL-NN, continuing 20..28), phase='answer', difficulty, family,
  trace_id (= uuid5(DNS, case).hex, same as the harness/harvest keying), session_id
  (= 'session-' + lowercased case), prompt, want_answer.

Idempotent: rewrites only the growth rows in the target file, leaving 07–15 intact.
This authors the corpus; it does NOT run any live model (the live A/B sweep is the
separately-gated, budget-spending step).

Output (default): appends to cache/model_ab_answer/ui_batch.jsonl + rebuilds
l2l3_batch.jsonl via build_l2l3_corpus.filter_l2l3.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
UI_BATCH = AGENT_ROOT / "cache" / "model_ab_answer" / "ui_batch.jsonl"

# (case, difficulty, prompt, want_answer). gj_id is assigned sequentially below.
GROWTH_CASES: tuple[tuple[str, str, str, str], ...] = (
    (
        "GEN-L2-multi-file-reconcile-16",
        "L2",
        "In /workspace/invoices2/ there are five invoice files (inv2-1.txt … "
        "inv2-5.txt). Each has an 'amount:' line and a 'status:' line. Sum the "
        "amounts of only the invoices whose status is 'paid', then write that "
        "subtotal to /workspace/out/paid2.txt and report it. Read every invoice "
        "before computing.",
        "the subtotal of paid invoices, also written to out/paid2.txt",
    ),
    (
        "GEN-L2-cross-ref-lookup-17",
        "L2",
        "Read /workspace/orders2.csv (order_id,customer_id) and "
        "/workspace/customers2.csv (customer_id,region). For each order, resolve "
        "its customer's region, then report how many orders fall in each region as "
        "a sorted list 'region: count'.",
        "per-region order counts",
    ),
    (
        "GEN-L2-pipeline-transform-18",
        "L2",
        "Read /workspace/events2.log. Keep only the lines containing 'ERROR', "
        "extract the timestamp at the start of each, count errors per hour, and "
        "report the single hour with the most errors. Write the full per-hour table "
        "to /workspace/out/errors2_by_hour.txt as well.",
        "the peak error hour plus the per-hour table file",
    ),
    (
        "GEN-L2-multi-source-synthesis-19",
        "L2",
        "You have three reports in /workspace/reports2/ (r1.txt, r2.txt, r3.txt), "
        "each ending with a 'TOTAL: N' line. Read all three, compute the "
        "period-over-period growth rate between consecutive reports, and report both "
        "growth rates (r1→r2 and r2→r3) as percentages to one decimal place. Note "
        "that a decline is a negative growth rate.",
        "the two period-over-period growth percentages (one is negative)",
    ),
    (
        "GEN-L2-dependency-resolve-20",
        "L2",
        "Read /workspace/deps2.txt where each line is 'A -> B' meaning A depends on "
        "B. Produce a valid install order (a topological sort) such that every "
        "dependency is installed before the thing that needs it, and report the "
        "order. If there is a cycle, report which nodes form it instead.",
        "a valid topological install order (or the cycle)",
    ),
    (
        "GEN-L3-constraint-solve-21",
        "L3",
        "In /workspace/schedule2/ there are availability files for five people "
        "(q1.txt … q5.txt), each listing the 30-minute slots they are free on "
        "Monday. Find a single 30-minute slot that works for at least four of the "
        "five people, preferring the earliest such slot, and report it together with "
        "who can and cannot attend. If no slot works for four people, say so and "
        "report the best slot you found.",
        "the earliest slot covering >=4 people plus the attendee split",
    ),
    (
        "GEN-L2-verify-and-fix-22",
        "L2",
        "Read /workspace/config2.json. Validate that it has both a 'host' and a "
        "'port' key and that 'port' is an integer between 1 and 65535. If anything "
        "is missing or invalid, write a corrected version to "
        "/workspace/out/config2.fixed.json using host='localhost' and port=8080 for "
        "any bad or missing field, and report exactly what you changed.",
        "the validation result and list of corrections made",
    ),
    (
        "GEN-L3-multi-hop-synthesis-23",
        "L3",
        "Read /workspace/memos/ (memo-1.txt … memo-4.txt). Each memo cites others by "
        "their number in a 'cites:' line. Build the citation graph, find the memo "
        "cited by the most others, then summarise THAT memo's key claim and explain "
        "which memos depend on it and why. Read every memo before answering.",
        "the most-cited memo, its claim, and its dependents",
    ),
    (
        "GEN-L3-iterative-refine-24",
        "L3",
        "Read /workspace/budget2.csv (category,planned,actual). Identify every "
        "category over budget, compute the total overrun, then propose a set of cuts "
        "to under-budget categories that fully offsets the overrun WITHOUT cutting "
        "any category below its actual spend. Report the proposed cuts and verify "
        "the offset balances to zero.",
        "a balanced set of offsetting cuts with the verification",
    ),
)

GJ_ID_START = 20  # existing rows use GJ-ABGENL-11..19


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for offset, (case, difficulty, prompt, want) in enumerate(GROWTH_CASES):
        rows.append(
            {
                "case": case,
                "gj_id": f"GJ-ABGENL-{GJ_ID_START + offset}",
                "phase": "answer",
                "difficulty": difficulty,
                "family": "general",
                "trace_id": uuid.uuid5(uuid.NAMESPACE_DNS, case).hex,
                "session_id": "session-" + case.lower(),
                "prompt": prompt,
                "want_answer": want,
            }
        )
    return rows


def append_growth_rows(ui_batch: Path = UI_BATCH) -> int:
    """Append the growth rows to ui_batch.jsonl (idempotent: replace, don't dup)."""
    growth_cases = {c for c, *_ in GROWTH_CASES}
    existing = [
        json.loads(line) for line in ui_batch.read_text().splitlines() if line.strip()
    ]
    kept = [r for r in existing if r.get("case") not in growth_cases]
    out = kept + build_rows()
    ui_batch.write_text("\n".join(json.dumps(r) for r in out) + "\n")
    return len(build_rows())


if __name__ == "__main__":
    n = append_growth_rows()
    print(f"appended {n} growth corpus rows -> {UI_BATCH}")

    # Rebuild the L2/L3 filtered batch from the updated source.
    from scripts.build_l2l3_corpus import filter_l2l3, write_jsonl

    l2l3 = filter_l2l3(UI_BATCH)
    write_jsonl(l2l3)
    print(f"rebuilt l2l3_batch.jsonl: {len(l2l3)} L2/L3 rows")
