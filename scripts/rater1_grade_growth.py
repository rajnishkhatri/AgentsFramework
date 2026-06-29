"""Rater-1 blind grading of the 9 growth L2/L3 cases (16-24).

Phase 2 of docs/plans/model_ab_l2l3_blind_adjudication.plan.md, for the growth
batch. Grades each blind item against its case's fixture-derived ground truth WITHOUT
opening the sealed arm key (the bias guardrail). Emits:
  - cache/model_ab_answer/l2l3_growth_labels_rater1.jsonl  (item_id -> label)
  - cache/model_ab_answer/l2l3_growth_rater2_worksheet.md   (for the human rater-2)

Label vocabulary: correct / partial / wrong, + confidence (high|low) + a one-line
justification citing the rubric. Truncated-at-source answers (cut at the 500-char
harvest clip before stating the load-bearing conclusion) are graded on what is
VISIBLE and flagged low-confidence so rater-2 reviews them — never guessed.

Ground truth per case is the fixture computation (verified in
seed_model_ab_l2l3_workspace.py), NOT a model's self-report.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

AD = Path(__file__).resolve().parent.parent / "cache" / "model_ab_answer"
BLIND = AD / "l2l3_growth_blind_items.jsonl"
LABELS = AD / "l2l3_growth_labels_rater1.jsonl"
WORKSHEET = AD / "l2l3_growth_rater2_worksheet.md"


def _norm(s: str) -> str:
    return re.sub(r"[\s,]+", " ", s.lower())


def grade(case: str, ans: str) -> tuple[str, str, str]:
    """Return (label, confidence, justification) for one answer.

    Deterministic checks keyed on the fixture ground truth. A 'partial' is a
    correct-but-incomplete or truncated-before-conclusion answer.
    """
    a = _norm(ans)
    truncated = len(ans) >= 498 and not ans.rstrip().endswith((".", "`", "*", ")"))

    if case == "GEN-L2-multi-file-reconcile-16":
        # paid subtotal must be 410 (inv2-1 200 + inv2-2 60 + inv2-4 150)
        if "410" in a and "475" not in a:
            return (
                "correct",
                "high",
                "paid subtotal=410 from inv2-1/2/4; 90+25 correctly unpaid",
            )
        if "475" in a:
            return (
                "wrong",
                "high",
                "reports 475 (used wrong/original fixtures, not invoices2)",
            )
        return "partial", "low", "no clear 410 subtotal stated"

    if case == "GEN-L2-cross-ref-lookup-17":
        ok = all(t in a for t in ("east: 4", "west: 3", "north: 1")) or all(
            t in a for t in ("east 4", "west 3", "north 1")
        )
        if ok:
            return "correct", "high", "region counts east:4/west:3/north:1 match"
        return "wrong", "high", "region counts do not match east:4/west:3/north:1"

    if case == "GEN-L2-pipeline-transform-18":
        peak15 = ("15" in a) and (
            "4 error" in a or "count | 4" in a or "| 4" in a or "15 | 4" in a
        )
        table = "13" in a and "14" in a and "15" in a
        if peak15 and table:
            return "correct", "high", "peak hour 15 (4 errors); per-hour 13=2/14=1/15=4"
        if peak15:
            return (
                "partial",
                "low",
                "peak 15 stated but per-hour table unclear/truncated",
            )
        return "wrong", "high", "peak hour != 15"

    if case == "GEN-L2-multi-source-synthesis-19":
        neg25 = "-25" in a or "−25" in a or "-0.25" in a or "decline" in a
        pos20 = "20" in a
        if neg25 and pos20:
            return "correct", "high", "r1->r2 = -25% (decline), r2->r3 = +20%"
        if pos20 and not neg25:
            return "wrong", "high", "first growth not negative/-25%"
        return "partial", "low", "growth rates incomplete/truncated"

    if case == "GEN-L2-dependency-resolve-20":
        # valid topo: V before Z before {X,Y} before W. Accept V,Z,X,Y,W or V,Z,Y,X,W.
        # The answer lists the dependency EDGES (W->X, X->Z, ...) before stating the
        # install order, so a naive first-5-letters scan reads the edge list, not the
        # order. Instead find the install-order STATEMENT: a run of all five nodes that
        # starts with V and ends with W (the unique deps-first shape).
        # Find an explicit ordered sequence of the five distinct nodes: a contiguous
        # run "v <sep> z <sep> x <sep> y <sep> w" where <sep> is comma / arrow / "then"
        # / whitespace / a numbered-list step. The dependency-edge listing never forms
        # a single contiguous 5-distinct-node run starting at V, so this isolates the
        # stated install order. Try both the raw text and a step-number-stripped copy.
        sep = r"(?:\s*(?:,|->|→|then|;)?\s*|\s+|\)[^a-z]*\(?\s*|\d+\.\s*)"
        node = r"\*{0,2}([vzxyw])\*{0,2}"
        pat = re.compile(node + (sep + node) * 4)
        seen: list[str] = []
        for text in (a, re.sub(r"\b\d+\.\s*", " ", a)):
            for m in pat.finditer(text):
                cand = list(m.groups())
                if len(set(cand)) == 5 and cand[0] == "v":
                    seen = cand
                    break
            if seen:
                break
        # Fallback: a numbered list "1. V (prose) 2. Z (prose) ..." where parenthetical
        # prose between items defeats the contiguous matcher. `a` is newline-collapsed
        # (_norm), so match the node that immediately follows each "N." step marker.
        if not seen:
            steps = re.findall(r"\b\d+\.\s*\*{0,2}([vzxyw])\b", a)
            if len(steps) == 5 and len(set(steps)) == 5:
                seen = steps
        valid = (
            len(seen) == 5
            and seen[:2] == ["v", "z"]
            and seen[-1] == "w"
            and set(seen[2:4]) == {"x", "y"}
        )
        nocycle = "no cycle" in a or "no cycles" in a or "acyclic" in a
        if valid and nocycle:
            return "correct", "high", f"valid topo {','.join(seen).upper()}; no cycle"
        if valid:
            return "partial", "low", "order valid but cycle-claim unclear"
        return "wrong", "high", f"order {seen} violates deps-first (need V,Z,..,W)"

    if case == "GEN-L3-constraint-solve-21":
        slot = "09:00" in a or "9:00" in a
        attend = all(q in a for q in ("q1", "q2", "q4", "q5"))
        if slot and attend:
            return "correct", "high", "earliest >=4 slot 09:00 with q1,q2,q4,q5"
        if slot:
            return (
                "partial",
                "low",
                "09:00 stated but attendee set incomplete/truncated",
            )
        return "wrong", "high", "earliest slot != 09:00"

    if case == "GEN-L2-verify-and-fix-22":
        host = "host" in a and ("missing" in a or "absent" in a or "did not exist" in a)
        port = (
            ("port" in a)
            and ("abc" in a)
            and ("integer" in a or "string" in a or "not an int" in a)
        )
        if host and port:
            return (
                "correct",
                "high",
                "both defects reported: host missing + port 'abc' non-int",
            )
        if host or port:
            return "partial", "low", "only one of the two defects clearly reported"
        return "wrong", "high", "neither defect correctly identified"

    if case == "GEN-L3-multi-hop-synthesis-23":
        m2_most = ("memo 2" in a or "memo-2" in a or "memo2" in a) and (
            "3 citation" in a
            or "cited by 3" in a
            or "1, 3, 4" in a
            or "1,3,4" in a
            or "most cited" in a
        )
        if m2_most and ("most cited" in a or "most-cited" in a):
            return "correct", "high", "memo-2 most-cited (by m1,m3,m4); claim present"
        if truncated and ("memo 2" in a or "memo-2" in a):
            return (
                "partial",
                "low",
                "graph correct so far but conclusion truncated at 500c",
            )
        if m2_most:
            return (
                "partial",
                "low",
                "memo-2 citers right; explicit 'most-cited' label unclear",
            )
        return "wrong", "high", "most-cited memo != memo-2"

    if case == "GEN-L3-iterative-refine-24":
        overrun = "80" in a and ("salaries" in a) and ("over" in a)
        # a valid cut set sums to 80 from under-budget (tools slack 100, events slack 70)
        cuts = "cut" in a or "offset" in a or "reduc" in a
        if overrun and cuts:
            return (
                "correct",
                "high",
                "salaries over by 80; offsetting cuts from under-budget",
            )
        if overrun:
            return (
                "partial",
                "low",
                "overrun 80 identified but cut set unclear/truncated",
            )
        return "wrong", "high", "overrun != 80 or salaries not identified"

    return "partial", "low", "no grader for case"


def main() -> None:
    items = [
        json.loads(line) for line in BLIND.read_text().splitlines() if line.strip()
    ]
    labels = []
    for it in items:
        label, conf, why = grade(it["case"], it["model_answer"])
        labels.append(
            {
                "item_id": it["item_id"],
                "case": it["case"],
                "label": label,
                "confidence": conf,
                "justification": why,
            }
        )
    LABELS.write_text("\n".join(json.dumps(x) for x in labels) + "\n")

    # rater-2 worksheet: every low-confidence + every partial + every wrong, plus a
    # sample of high-confidence correct (1 per case) for spot-checking.
    from collections import Counter, defaultdict

    by_case = defaultdict(list)
    item_by_id = {it["item_id"]: it for it in items}
    for lab in labels:
        by_case[lab["case"]].append(lab)

    dist = Counter(lab["label"] for lab in labels)
    review = [
        lab
        for lab in labels
        if lab["confidence"] == "low" or lab["label"] in ("partial", "wrong")
    ]
    # add one high-conf correct per case as a spot-check
    spot = []
    for case, labs in by_case.items():
        hc = [x for x in labs if x["confidence"] == "high" and x["label"] == "correct"]
        if hc:
            spot.append(hc[0])

    lines = ["# Rater-2 Worksheet — L2/L3 Growth Cases (16-24)", ""]
    lines.append(
        "> You are **rater-2**. Grade each item below `correct` / `partial` / `wrong` "
        "from the rubric, independently of rater-1's label (shown for reconciliation, "
        "not to anchor you). The sealed arm key is NOT opened until your labels are frozen."
    )
    lines.append("")
    lines.append(
        f"**Rater-1 label distribution:** {dict(dist)} over {len(labels)} items."
    )
    lines.append("")
    lines.append(f"## A. Must-review ({len(review)}): low-confidence / partial / wrong")
    lines.append("")
    for lab in review:
        it = item_by_id[lab["item_id"]]
        lines.append(f"### [{lab['item_id'][:10]}] {lab['case']}")
        lines.append(
            f"- **rater-1:** {lab['label']} ({lab['confidence']}) — {lab['justification']}"
        )
        lines.append(
            f"- **rubric:** {json.dumps(it['rubric'].get('must_have_facts', []))}"
        )
        lines.append(f"- **answer:** {it['model_answer'][:600]!r}")
        lines.append("- **rater-2 label:** ____  (correct/partial/wrong)  note: ____")
        lines.append("")
    lines.append(
        f"## B. Spot-check ({len(spot)}): one high-confidence 'correct' per case"
    )
    lines.append("")
    for lab in spot:
        it = item_by_id[lab["item_id"]]
        lines.append(f"### [{lab['item_id'][:10]}] {lab['case']}")
        lines.append(f"- **rater-1:** correct (high) — {lab['justification']}")
        lines.append(f"- **answer:** {it['model_answer'][:400]!r}")
        lines.append("- **rater-2 agrees? (y/n):** ____")
        lines.append("")

    WORKSHEET.write_text("\n".join(lines) + "\n")
    print(f"rater-1 labels -> {LABELS} ({len(labels)} items)")
    print(f"label dist: {dict(dist)}")
    print(f"rater-2 worksheet -> {WORKSHEET} (review={len(review)}, spot={len(spot)})")


if __name__ == "__main__":
    main()
