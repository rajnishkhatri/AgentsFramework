"""Build the detailed case-by-case rater-2 worksheet for the 9 GROWTH cases (16-24).

Mirrors the structure of cache/model_ab_answer/l2l3_rater_worksheet_detailed.md (the
original 9-case detailed worksheet) but for the Wave-1 growth batch. For each case it
emits: the prompt, the ACTUAL fixture file contents the model read (from <repo>/workspace),
a worked ground-truth derivation, the rubric, and every blind model answer with a Verdict
line to fill.

Blinding guarantee: this reads ONLY l2l3_growth_blind_items.jsonl (shuffled, arm-free)
and the on-disk fixtures + the GROUND_TRUTH the seeder authors. It NEVER opens
l2l3_growth_arm_key.sealed.json. Rater-1's labels are intentionally OMITTED so rater-2
is not anchored.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from seed_model_ab_l2l3_workspace import GROUND_TRUTH_BY_CASE  # noqa: E402

AGENT_ROOT = Path(__file__).resolve().parent.parent
AD = AGENT_ROOT / "cache" / "model_ab_answer"
WS = AGENT_ROOT / "workspace"
BLIND = AD / "l2l3_growth_blind_items.jsonl"
OUT = AD / "l2l3_growth_rater_worksheet_detailed.md"

# Display order = case number ascending (16..24), readable for the rater.
CASE_ORDER = [
    "GEN-L2-multi-file-reconcile-16",
    "GEN-L2-cross-ref-lookup-17",
    "GEN-L2-pipeline-transform-18",
    "GEN-L2-multi-source-synthesis-19",
    "GEN-L2-dependency-resolve-20",
    "GEN-L3-constraint-solve-21",
    "GEN-L2-verify-and-fix-22",
    "GEN-L3-multi-hop-synthesis-23",
    "GEN-L3-iterative-refine-24",
]

# Per-case: which fixture files (relative to workspace) the model read, and the
# worked-truth narrative that DERIVES the rubric so the rater can verify it themselves.
CASE_META: dict[str, dict] = {
    "GEN-L2-multi-file-reconcile-16": {
        "fixtures": [
            "invoices2/inv2-1.txt",
            "invoices2/inv2-2.txt",
            "invoices2/inv2-3.txt",
            "invoices2/inv2-4.txt",
            "invoices2/inv2-5.txt",
        ],
        "worked": (
            "Sum the `amount` of invoices whose `status: paid`.\n\n"
            "- inv2-1 = 200 **paid**\n"
            "- inv2-2 = 60 **paid**\n"
            "- inv2-3 = 90 unpaid (excluded)\n"
            "- inv2-4 = 150 **paid**\n"
            "- inv2-5 = 25 unpaid (excluded)\n\n"
            "paid subtotal = 200 + 60 + 150 = **410**. (90 + 25 = 115 unpaid are correctly left out.)"
        ),
        "grading": (
            "**correct** = states paid subtotal 410 (and ideally names inv2-1/2/4). "
            "**partial** = right method but no clear 410, or truncated before the total. "
            "**wrong** = reports 475 (used the *original* `invoices/` fixtures), any other "
            "total, or gave up on file access."
        ),
    },
    "GEN-L2-cross-ref-lookup-17": {
        "fixtures": ["orders2.csv", "customers2.csv"],
        "worked": (
            "Join orders2→customers2 on `customer_id`, tally by region.\n\n"
            "customers: c1=east, c2=east, c3=west, c4=north, c5=west.\n\n"
            "orders: o1→c1, o2→c3, o3→c1, o4→c4, o5→c2, o6→c5, o7→c3, o8→c1.\n\n"
            "- **east** = c1(o1,o3,o8) + c2(o5) = **4**\n"
            "- **west** = c3(o2,o7) + c5(o6) = **3**\n"
            "- **north** = c4(o4) = **1**"
        ),
        "grading": (
            "**correct** = east 4, west 3, north 1 (all three). "
            "**partial** = some counts right, one wrong/missing. "
            "**wrong** = wrong counts, gave up, or answered a different question. "
            "Note: the *original* case-08 answer was north:4/south:2/west:1 — that shape "
            "here is **wrong** (different fixtures)."
        ),
    },
    "GEN-L2-pipeline-transform-18": {
        "fixtures": ["events2.log"],
        "worked": (
            "Count `ERROR` lines per hour (HH from the HH:MM:SS timestamp); find the peak hour.\n\n"
            "- 13:xx → ERROR disk, ERROR net = **2**\n"
            "- 14:xx → ERROR timeout = **1** (14:55 is WARN, not ERROR)\n"
            "- 15:xx → ERROR oom, ERROR oom, ERROR timeout, ERROR disk = **4**\n\n"
            "peak error hour = **15** (4 errors). Per-hour table: 13=2, 14=1, 15=4."
        ),
        "grading": (
            "**correct** = peak hour 15 with the per-hour table 13=2/14=1/15=4. "
            "**partial** = peak 15 stated but the per-hour breakdown is missing/truncated. "
            "**wrong** = any peak hour ≠ 15."
        ),
    },
    "GEN-L2-multi-source-synthesis-19": {
        "fixtures": ["reports2/r1.txt", "reports2/r2.txt", "reports2/r3.txt"],
        "worked": (
            "Read each TOTAL, compute consecutive growth rates.\n\n"
            "- r1 TOTAL = 400, r2 TOTAL = 300, r3 TOTAL = 360.\n"
            "- r1→r2 = (300 − 400) / 400 = **−25%** (a DECLINE — the sign matters)\n"
            "- r2→r3 = (360 − 300) / 300 = **+20%**"
        ),
        "grading": (
            "**correct** = first rate −25% (negative/decline) AND second +20%. "
            "**partial** = rates incomplete or truncated. "
            "**wrong** = first growth not negative / not −25% (e.g. reported +25%)."
        ),
    },
    "GEN-L2-dependency-resolve-20": {
        "fixtures": ["deps2.txt"],
        "worked": (
            "Edges in `deps2.txt` are `X -> Y` meaning **X depends on Y** "
            "(Y must be installed first).\n\n"
            "- W → X, W → Y  (W depends on X and Y)\n"
            "- X → Z, Y → Z  (X and Y depend on Z)\n"
            "- Z → V         (Z depends on V)\n\n"
            "Deps-first install order: **V, Z, then X and Y (either order), then W** → "
            "`V, Z, X, Y, W` (or `V, Z, Y, X, W`). The graph is acyclic (no cycle)."
        ),
        "grading": (
            "**correct** = an order with V first, then Z, then {X,Y} in either order, then W, "
            "AND a no-cycle/acyclic statement. "
            "**partial** = valid order but the cycle claim is unclear/absent. "
            "**wrong** = any order violating deps-first (e.g. lists the dependency EDGES as the "
            "order, or W first). Watch for answers that echo the `W -> X` edge listing instead "
            "of stating the install order."
        ),
    },
    "GEN-L3-constraint-solve-21": {
        "fixtures": [
            "schedule2/q1.txt",
            "schedule2/q2.txt",
            "schedule2/q3.txt",
            "schedule2/q4.txt",
            "schedule2/q5.txt",
        ],
        "worked": (
            "Find the earliest 30-min slot free for ≥4 of the 5 people.\n\n"
            "- q1 {08:30, 09:00}, q2 {09:00, 09:30}, q3 {08:30, 09:30}, "
            "q4 {09:00, 10:00}, q5 {09:00}\n\n"
            "Per slot: 08:30 → q1,q3 = 2 · **09:00 → q1,q2,q4,q5 = 4** · 09:30 → q2,q3 = 2 · "
            "10:00 → q4 = 1.\n\n"
            "Earliest covering ≥4 = **09:00**; attendees **q1, q2, q4, q5** (q3 absent). "
            "It's the *only* slot reaching 4."
        ),
        "grading": (
            "**correct** = slot 09:00 AND attendee set q1,q2,q4,q5 (q3 absent). "
            "**partial** = 09:00 stated but the attendee set is incomplete/truncated. "
            "**wrong** = any slot ≠ 09:00."
        ),
    },
    "GEN-L2-verify-and-fix-22": {
        "fixtures": ["config2.json"],
        "worked": (
            "Validate the config; it has **two** defects.\n\n"
            '- `config2.json` = `{"port": "abc", "timeout": 30}`\n'
            "- Defect 1: the `host` key is **missing** (absent entirely).\n"
            '- Defect 2: `port` is the string `"abc"` — **not an integer** in 1..65535.\n\n'
            "A correct answer reports BOTH and writes a corrected config with a host and a "
            "valid integer port."
        ),
        "grading": (
            "**correct** = BOTH defects reported (host missing AND port 'abc' non-integer). "
            "**partial** = only one of the two defects clearly reported. "
            "**wrong** = neither defect correctly identified."
        ),
    },
    "GEN-L3-multi-hop-synthesis-23": {
        "fixtures": [
            "memos/memo-1.txt",
            "memos/memo-2.txt",
            "memos/memo-3.txt",
            "memos/memo-4.txt",
        ],
        "worked": (
            "Build the citation graph from each memo's `cites:` line, find the most-cited memo.\n\n"
            "- memo-1 cites 2, memo-2 cites 1, memo-3 cites 2, memo-4 cites 2.\n"
            "- So memo-2 is cited by m1, m3, m4 → **cited by 3** (the most). "
            "(memo-1 is cited only by m2 → 1.)\n\n"
            "Most-cited = **memo-2**; its claim: *error budgets must precede feature work*; "
            "its citers are **memo-1, memo-3, memo-4**."
        ),
        "grading": (
            "**correct** = most-cited = memo-2 (cited by 3), with the citers and/or claim. "
            "**partial** = memo-2 graph right but the explicit 'most-cited' conclusion is "
            "truncated/unclear (several answers here are clipped at the 500-char harvest "
            "boundary — judge on the visible content). "
            "**wrong** = most-cited ≠ memo-2."
        ),
    },
    "GEN-L3-iterative-refine-24": {
        "fixtures": ["budget2.csv"],
        "worked": (
            "Find the over-budget category and propose offsetting cuts from under-budget "
            "categories that balance to zero without cutting any category below its actual.\n\n"
            "- salaries: planned 1000, actual 1080 → **over by 80**\n"
            "- tools: planned 300, actual 200 → under, slack 100\n"
            "- travel: planned 150, actual 150 → exact, slack 0\n"
            "- events: planned 250, actual 180 → under, slack 70\n\n"
            "Total overrun = **80**. Valid cut sets sum to 80 from tools(≤100)/events(≤70) "
            "slack — e.g. tools −80, or tools −50 + events −30."
        ),
        "grading": (
            "**correct** = overrun 80 on salaries identified AND offsetting cuts that sum to 80 "
            "from under-budget categories. "
            "**partial** = overrun 80 identified but the cut set is unclear/truncated. "
            "**wrong** = overrun ≠ 80 or salaries not identified."
        ),
    },
}


def _read_fixture(rel: str) -> str:
    p = WS / rel
    try:
        return p.read_text()
    except OSError:
        return "(fixture not found on disk)"


def main() -> None:
    items = [
        json.loads(line) for line in BLIND.read_text().splitlines() if line.strip()
    ]
    by_case: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_case[it["case"]].append(it)
    # stable answer order within a case = by item_id (deterministic, arm-free)
    for case in by_case:
        by_case[case].sort(key=lambda x: x["item_id"])

    total = len(items)
    L: list[str] = []
    L.append(
        "# L2/L3 GROWTH Rater Worksheet — Detailed Case-by-Case Walkthrough (cases 16–24)"
    )
    L.append("")
    L.append(
        "Grade each blind item **correct / partial / wrong** against the rubric. You are "
        "BLIND to which model produced each answer (all 4 arms share the same 9 cases). "
        "Each case gives: the **prompt**, the **fixture files** the model read, the "
        "**worked ground truth**, the **rubric**, then every model answer with a "
        "**Verdict** line to fill."
    )
    L.append("")
    L.append(
        "> Do NOT open `l2l3_growth_arm_key.sealed.json` until all verdicts are recorded "
        "— that is the blinding guarantee. Rater-1's labels are intentionally omitted here "
        "so they do not anchor you."
    )
    L.append("")
    L.append(
        f"**Total items to grade: {total}** across {len(CASE_ORDER)} cases (4 answers each)."
    )
    L.append("")
    L.append("---")
    L.append("")

    for n, case in enumerate(CASE_ORDER, 1):
        meta = CASE_META[case]
        gt = GROUND_TRUTH_BY_CASE[case]
        case_items = by_case[case]
        prompt = case_items[0]["prompt"]
        rubric = case_items[0]["rubric"]

        L.append(f"## Case {n}/9 — `{case}`")
        L.append("")
        L.append("### Prompt (input)")
        L.append("")
        L.append(f"> {prompt}")
        L.append("")
        L.append("### Fixture files (what the model read)")
        L.append("")
        for rel in meta["fixtures"]:
            L.append(f"**`workspace/{rel}`**")
            L.append("")
            L.append("```")
            L.append(_read_fixture(rel).rstrip("\n"))
            L.append("```")
            L.append("")
        L.append("### Worked ground truth")
        L.append("")
        L.append(meta["worked"])
        L.append("")
        L.append(f"> **GRADING:** {meta['grading']}")
        L.append("")
        L.append("### Rubric (must-have facts)")
        L.append("")
        for fact in rubric.get("must_have_facts", gt.facts):
            L.append(f"- {fact}")
        av = rubric.get("acceptable_variation", list(gt.notes))
        if av:
            L.append("")
            L.append(f"*Acceptable variation:* {'; '.join(av)}")
        L.append("")
        L.append(f"### Answers to grade ({len(case_items)})")
        L.append("")
        for it in case_items:
            ans = it["model_answer"]
            clipped = len(ans) >= 498
            L.append(f"#### Item `{it['item_id']}`")
            L.append("")
            if clipped:
                L.append(
                    "> ⚠️ This answer is clipped at the 500-char harvest boundary — "
                    "the load-bearing conclusion may be cut off. Judge on what is visible."
                )
                L.append("")
            L.append("**Model answer**")
            L.append("")
            L.append("```text")
            L.append(ans.rstrip("\n"))
            L.append("```")
            L.append("")
            L.append("**Verdict:** `______` (correct / partial / wrong) — *reason:*")
            L.append("")
        L.append("---")
        L.append("")

    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT} ({total} items across {len(CASE_ORDER)} cases)")


if __name__ == "__main__":
    main()
