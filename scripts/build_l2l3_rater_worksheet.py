"""Build the DETAILED case-by-case rater worksheet for L2/L3 blind adjudication.

Phase 3 support (docs/plans/model_ab_l2l3_blind_adjudication.plan.md). Unlike the
terse worksheet, this emits, per case: the prompt, the seeded fixture INPUTS the
model actually read, a worked GROUND-TRUTH derivation, the rubric, and then every
blind (anonymized) model answer with a verdict line — so a rater can grade
thoroughly with all context in one document. NO arm/model identity appears; items
stay shuffled and keyed only by item_id (the sealed key is opened later).

Inputs:
  cache/model_ab_answer/l2l3_blind_items.jsonl   (blind answers + rubric)
  workspace/<fixtures>                            (the seeded inputs, read live)
  scripts/seed_model_ab_l2l3_workspace.GROUND_TRUTH (fact list)

Output:
  cache/model_ab_answer/l2l3_rater_worksheet_detailed.md
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.seed_model_ab_l2l3_workspace import GROUND_TRUTH_BY_CASE

AGENT_ROOT = Path(__file__).resolve().parent.parent
ANSWER_DIR = AGENT_ROOT / "cache" / "model_ab_answer"
WORKSPACE = AGENT_ROOT / "workspace"
BLIND = ANSWER_DIR / "l2l3_blind_items.jsonl"
BATCH = ANSWER_DIR / "l2l3_batch.jsonl"
OUT = ANSWER_DIR / "l2l3_rater_worksheet_detailed.md"

# The fixture files each case reads (relative to workspace/).
FIXTURE_FILES: dict[str, list[str]] = {
    "GEN-L2-multi-file-reconcile-07": [
        "invoices/inv-1.txt", "invoices/inv-2.txt", "invoices/inv-3.txt",
        "invoices/inv-4.txt", "invoices/inv-5.txt",
    ],
    "GEN-L2-cross-ref-lookup-08": ["orders.csv", "customers.csv"],
    "GEN-L2-pipeline-transform-09": ["events.log"],
    "GEN-L2-multi-source-synthesis-10": [
        "reports/q1.txt", "reports/q2.txt", "reports/q3.txt",
    ],
    "GEN-L2-verify-and-fix-11": ["config.json"],
    "GEN-L2-dependency-resolve-12": ["deps.txt"],
    "GEN-L3-constraint-solve-13": [
        "schedule/p1.txt", "schedule/p2.txt", "schedule/p3.txt",
        "schedule/p4.txt", "schedule/p5.txt",
    ],
    "GEN-L3-multi-hop-synthesis-14": [
        "papers/paper-1.txt", "papers/paper-2.txt",
        "papers/paper-3.txt", "papers/paper-4.txt",
    ],
    "GEN-L3-iterative-refine-15": ["budget.csv"],
}

# A worked, human-readable derivation of the correct answer from the inputs. This
# is the "how to grade" reasoning a rater needs — derived ONLY from the seeded
# fixtures (no model output), so it is ground truth.
WORKED_REASONING: dict[str, str] = {
    "GEN-L2-multi-file-reconcile-07": (
        "Read all 5 invoices. Keep only status: paid → inv-1 (100), inv-3 (75), "
        "inv-4 (300). Sum = 100+75+300 = **475**. inv-2 (250) and inv-5 (40) are "
        "unpaid and excluded. The prompt requires the subtotal ALSO be written to "
        "`/workspace/out/paid.txt` (a real file write), then reported.\n\n"
        "GRADING: correct = 475 reported AND written to out/paid.txt. partial = "
        "475 correct but write missing or to the wrong path. wrong = wrong sum, "
        "gave up, or off-task."
    ),
    "GEN-L2-cross-ref-lookup-08": (
        "Join orders→customers on customer_id, then tally by region.\n"
        "customers: c1=north, c2=south, c3=north, c4=west.\n"
        "orders: o1→c1, o2→c2, o3→c1, o4→c3, o5→c4, o6→c2, o7→c1.\n"
        "north = o1,o3,o7 (c1) + o4 (c3) = **4**; south = o2,o6 (c2) = **2**; "
        "west = o5 (c4) = **1**.\n\n"
        "GRADING: correct = north 4, south 2, west 1 (all three). partial = some "
        "counts right, one wrong/missing. wrong = wrong counts, gave up, or "
        "answered a different question (e.g. 'most orders', '% north')."
    ),
    "GEN-L2-pipeline-transform-09": (
        "Keep ERROR lines, bucket by leading hour.\n"
        "08:15 ERROR (1) · 09:02, 09:10, 09:59 ERROR (3) · 10:30 ERROR (1).\n"
        "Per-hour: 08=1, 09=3, 10=1. Peak hour = **09** (3 errors). The prompt "
        "also requires writing the per-hour table to "
        "`/workspace/out/errors_by_hour.txt`.\n\n"
        "GRADING: correct = peak 09 AND table 08=1/09=3/10=1 (write expected). "
        "partial = peak+table right but no file write. wrong = wrong hour, counted "
        "total ERRORs instead of per-hour, gave up, or off-task."
    ),
    "GEN-L2-multi-source-synthesis-10": (
        "Totals: q1=200, q2=250, q3=300.\n"
        "q1→q2 = (250-200)/200 = **25.0%**. q2→q3 = (300-250)/250 = **20.0%**.\n\n"
        "GRADING: correct = both 25.0% and 20.0% (fraction 0.25/0.20 ok if "
        "labeled). partial = one right. wrong = wrong values, summed totals "
        "(=750) instead of growth, gave up, or off-task."
    ),
    "GEN-L2-verify-and-fix-11": (
        "config.json = {\"host\": \"db.internal\", \"port\": 70000}. host present; "
        "port 70000 is OUT of range 1..65535 → INVALID. The prompt says: for any "
        "bad field use host='localhost', port=8080, write the corrected file to "
        "`/workspace/out/config.fixed.json`, and report the change.\n"
        "Correct fix: port → 8080 (host may stay db.internal since it's present "
        "and valid; the prompt's localhost fallback is for BAD fields only).\n\n"
        "GRADING: correct = flags port 70000 out of range AND writes a corrected "
        "config with a valid port (8080). partial = flags the bad port but no "
        "corrected file written. wrong = fabricated/misread the config (e.g. "
        "claims port 8080 was already valid), gave up, or off-task."
    ),
    "GEN-L2-dependency-resolve-12": (
        "deps.txt: A→B, A→C, B→D, C→D, where 'X → Y' means X depends on Y (Y "
        "first). So D has no deps; B,C depend on D; A depends on B,C.\n"
        "Valid install order (dependency BEFORE dependent): **D, B, C, A** "
        "(B/C interchangeable). No cycle.\n\n"
        "GRADING: correct = D before B,C and B,C before A; no cycle. wrong = "
        "REVERSED order (A,B,C,D — installs A before its dependency D), gave up, "
        "or off-task. A reversed order is WRONG even though it 'looks' sorted."
    ),
    "GEN-L3-constraint-solve-13": (
        "Free slots: p1{9,10,11} p2{9,11} p3{9,10} p4{9,11} p5{10,11}.\n"
        "09:00 → p1,p2,p3,p4 = **4**. 10:00 → p1,p3,p5 = 3. 11:00 → p1,p2,p4,p5 "
        "= 4.\nBoth 09:00 and 11:00 cover 4; the prompt wants the EARLIEST → "
        "**09:00**, attendees p1,p2,p3,p4, absent p5.\n\n"
        "GRADING: correct = 09:00 chosen as earliest-covering-4 with p1,p2,p3,p4 "
        "(and p5 absent). partial = finds 09:00=4 but doesn't pick it as the "
        "earliest (e.g. lists slots at a >=3 threshold without choosing). wrong = "
        "wrong slot, gave up, or off-task."
    ),
    "GEN-L3-iterative-refine-15": (
        "budget.csv: food 100/130 (OVER by 30), travel 200/150 (under, slack 50), "
        "office 80/60 (under, slack 20), rent 500/500 (exact).\n"
        "Only food is over → total overrun = **30**. Offsetting cuts must come "
        "from under-budget categories WITHOUT cutting planned below actual: travel "
        "can give up to 50, office up to 20. A valid cut set sums to 30 (e.g. "
        "travel −30, or travel −20 + office −10) and balances the overrun to zero.\n\n"
        "GRADING: correct = overrun 30 identified AND a concrete cut set proposed "
        "that totals 30 without any category below its actual (offset = 0). "
        "partial = correct variance analysis but stops there / no balancing cut "
        "proposal. wrong = wrong overrun, 'budget is fine/under' with no cuts, "
        "gave up, or off-task."
    ),
    "GEN-L3-multi-hop-synthesis-14": (
        "cites lines: paper-1 cites 3, paper-2 cites 3, paper-4 cites 3, paper-3 "
        "cites nobody. So paper-3 is cited by 3 others → **most-cited = paper-3**. "
        "Its claim: 'temporal locality dominates real workloads'. Dependents "
        "(citers) = **paper-1, paper-2, paper-4**.\n\n"
        "GRADING: correct = most-cited is paper-3, cited by paper-1/2/4, claim "
        "summarized. partial = identifies paper-3 as foundational but doesn't "
        "resolve the citers (e.g. reads 'cites: 3' as a count, not a target). "
        "wrong = names the wrong paper (e.g. Paper 2), gave up, or off-task."
    ),
}


def _read_fixture(rel: str) -> str:
    p = WORKSPACE / rel
    try:
        return p.read_text()
    except OSError:
        return "(fixture not present — run seed_model_ab_l2l3_workspace.py)"


def _fence(text: str, info: str = "") -> str:
    """Fenced code block that survives embedded ``` in model answers."""
    marker = "```"
    while marker in text:
        marker += "`"
    opening = f"{marker}{info}" if info else marker
    return f"{opening}\n{text.rstrip()}\n{marker}"


def _format_worked_reasoning(text: str) -> str:
    """Render worked ground truth with paragraph breaks and a GRADING callout."""
    parts: list[str] = []
    for block in text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("GRADING:"):
            parts.append("> **GRADING:** " + block[len("GRADING:") :].strip())
            continue
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        parts.append("\n\n".join(lines))
    return "\n\n".join(parts)


def build() -> str:
    items = [json.loads(l) for l in BLIND.read_text().splitlines() if l.strip()]
    prompts = {
        json.loads(l)["case"]: json.loads(l)["prompt"]
        for l in BATCH.read_text().splitlines() if l.strip()
    }
    from collections import defaultdict
    by_case: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_case[it["case"]].append(it)

    case_count = len(by_case)
    sections: list[str] = [
        "\n\n".join(
            [
                "# L2/L3 Rater Worksheet — Detailed Case-by-Case Walkthrough",
                (
                    "Grade each blind item **correct / partial / wrong** against the "
                    "rubric. You are BLIND to which model produced each answer (every "
                    "arm shares the same 9 cases). Each case below gives: the "
                    "**prompt**, the **fixture inputs** the model read, the **worked "
                    "ground truth**, the **rubric**, and then every model answer "
                    "with a **Verdict** line to fill."
                ),
                (
                    "> Do NOT open `l2l3_arm_key.sealed.json` until all verdicts are "
                    "recorded — that is the blinding guarantee."
                ),
                (
                    f"**Total items to grade: {len(items)}** across "
                    f"{case_count} cases."
                ),
            ]
        )
    ]

    for n, case in enumerate(sorted(by_case), 1):
        gt = GROUND_TRUTH_BY_CASE[case]
        case_parts: list[str] = [
            "---",
            f"## Case {n}/{case_count} — `{case}`",
            f"### Prompt (input)\n\n> {prompts.get(case, '')}",
        ]

        fixture_blocks: list[str] = []
        for rel in FIXTURE_FILES.get(case, []):
            body = _read_fixture(rel).rstrip("\n")
            fixture_blocks.append(
                f"**`workspace/{rel}`**\n\n{_fence(body)}"
            )
        case_parts.append(
            "### Fixture inputs (what the model read)\n\n"
            + "\n\n".join(fixture_blocks)
        )

        case_parts.append(
            "### Worked ground truth\n\n"
            + _format_worked_reasoning(WORKED_REASONING[case])
        )

        rubric_lines = [f"- {fact}" for fact in gt.facts]
        if gt.notes:
            rubric_lines.append(
                "\n*Acceptable variation:* " + "; ".join(gt.notes)
            )
        case_parts.append(
            "### Rubric (must-have facts)\n\n" + "\n".join(rubric_lines)
        )

        answer_blocks: list[str] = []
        for it in by_case[case]:
            ans = it["model_answer"].strip()
            answer_blocks.append(
                "\n\n".join(
                    [
                        f"#### Item `{it['item_id']}`",
                        "**Model answer**",
                        _fence(ans, "text"),
                        (
                            "**Verdict:** `______` "
                            "(correct / partial / wrong) — *reason:*"
                        ),
                    ]
                )
            )
        case_parts.append(
            f"### Answers to grade ({len(by_case[case])})\n\n"
            + "\n\n".join(answer_blocks)
        )

        sections.append("\n\n".join(case_parts))

    return "\n\n".join(sections) + "\n"


if __name__ == "__main__":
    text = build()
    OUT.write_text(text)
    n = text.count("**Verdict:**")
    print(f"wrote detailed worksheet ({n} items) -> {OUT}")
