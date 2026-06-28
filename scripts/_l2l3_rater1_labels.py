"""Rater-1 (agent) BLIND labels for the L2/L3 adjudication set.

Phase 3 of docs/plans/model_ab_l2l3_blind_adjudication.plan.md. Each label is the
agent's blind verdict (correct/partial/wrong) against the Phase-1 rubric, with a
one-line justification citing the rubric and a confidence flag. Graded WITHOUT the
sealed arm key (blinding); the labels file is hashed before the key is opened.

VERDICT key per item_id (first 12 hex shown in the dump). Judgments:
  correct = all must-have rubric facts present and right.
  partial = some must-have facts right, others missing/wrong (or compute right but
            a required write/step omitted).
  wrong   = wrong numbers, gave up ("unable to access"), or answered a different
            prompt entirely (hallucination).
"""

from __future__ import annotations

import json
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
ANSWER_DIR = AGENT_ROOT / "cache" / "model_ab_answer"
BLIND = ANSWER_DIR / "l2l3_blind_items.jsonl"
OUT = ANSWER_DIR / "l2l3_labels_rater1.jsonl"

# item_id_prefix(12) -> (verdict, confidence, justification)
LABELS: dict[str, tuple[str, str, str]] = {
    # ── GEN-L2-cross-ref-lookup-08 (north:4 south:2 west:1) ──
    "2e0d19cf6c40": (
        "wrong",
        "high",
        "gave up + answered a different prompt (customer 42 latest order); no region counts",
    ),
    "2669ee43fcdf": (
        "correct",
        "high",
        "north 4, south 2, west 1 — all three counts correct",
    ),
    "f623fe114eb1": (
        "wrong",
        "high",
        "gave up: 'unable to access', no counts produced",
    ),
    "fa0caf89254b": ("correct", "high", "north 4, south 2, west 1 — correct"),
    "4af3f558dd85": (
        "wrong",
        "high",
        "answered a different question (most orders + % north); did not report per-region counts",
    ),
    "6006587114bc": ("correct", "high", "north 4, south 2, west 1 — correct"),
    # ── GEN-L2-dependency-resolve-12 (D before B,C; B,C before A; no cycle) ──
    "cf55f7a93230": (
        "correct",
        "high",
        "D, B, C, A — deps-first order correct; no cycle",
    ),
    "9c18000e4bef": (
        "wrong",
        "high",
        "hallucination: refuses, role-play preamble, no topo sort",
    ),
    "340b0ddf30fd": (
        "wrong",
        "high",
        "A,B,C,D is REVERSED — A installed before its dependency D; violates deps-first",
    ),
    "f64ba8686a71": ("correct", "high", "D,B,C,A written out; deps-first correct"),
    "24ee3d4ca021": ("wrong", "high", "gave up: 'unable to read deps.txt', no order"),
    "6bc71fa54ea3": (
        "wrong",
        "high",
        "A,B,C,D reversed — same deps-first violation as 340b",
    ),
    # ── GEN-L2-multi-file-reconcile-07 (paid 100+75+300=475 -> out/paid.txt) ──
    "987da4cd8be5": (
        "correct",
        "high",
        "475 subtotal + written to out/paid.txt; paid set correct",
    ),
    "18f180fd99e5": ("wrong", "high", "gave up: boundary error, no subtotal"),
    "31d6599c63df": (
        "partial",
        "low",
        "475 correct but written to output.txt not out/paid.txt",
    ),
    "17340957e59d": (
        "wrong",
        "high",
        "hallucination: answered a Svelte useEffect question",
    ),
    "d8dc107140ca": (
        "partial",
        "low",
        "475 correct, paid set correct, but saved to invoices/summary.txt not out/paid.txt",
    ),
    "1637cffff3fa": (
        "partial",
        "low",
        "475 paid subtotal correct but no write to out/paid.txt mentioned",
    ),
    # ── GEN-L2-multi-source-synthesis-10 (q1->q2 25%, q2->q3 20%) ──
    "2ba4b3f5dfb5": (
        "wrong",
        "high",
        "hallucination: flaky-UI-test debugging playbook, off task",
    ),
    "6d386b695450": (
        "wrong",
        "high",
        "gave up: 'unable to access reports', no growth rates",
    ),
    "0c4e897190d2": (
        "wrong",
        "high",
        "computed SUM=750 instead of the two growth rates; wrong task",
    ),
    "569ac22aa817": ("correct", "high", "25.0% and 20.0% — both growth rates correct"),
    "0d3bc320a381": ("correct", "high", "25% and 20% — correct"),
    "bee98e820177": ("correct", "high", "25.0% and 20.0% — correct"),
    # ── GEN-L2-pipeline-transform-09 (peak hour 09; 08=1,09=3,10=1 -> file) ──
    "6a307d891e61": ("correct", "high", "08=1,09=3,10=1; peak 09; output written"),
    "4a2dc16fa3a7": (
        "partial",
        "low",
        "per-hour table + peak 09 correct, but no out/errors_by_hour.txt write shown",
    ),
    "6929d618ee40": ("wrong", "high", "gave up: 'unable to access events.log'"),
    "551746ea687e": (
        "wrong",
        "high",
        "counted 5 total ERRORs; did not do per-hour or peak-hour task",
    ),
    "586630b5ec31": (
        "wrong",
        "high",
        "hallucination: Go //go:embed init-order bug, off task",
    ),
    "6bf77a6b3794": ("correct", "high", "08=1,09=3,10=1; peak 09; verified output"),
    # ── GEN-L2-verify-and-fix-11 (port 70000 invalid -> out/config.fixed.json) ──
    "2a02c9f4b021": (
        "wrong",
        "high",
        "gave up: refuses, asks for paste; no validation/fix",
    ),
    "d7c3efab39e2": (
        "partial",
        "low",
        "correctly flags port 70000 out of range, but no corrected file written",
    ),
    "4ca904f5ec77": (
        "wrong",
        "high",
        "fabricated config (host localhost/port 8080); did not read the real port 70000",
    ),
    "b205d8bbc673": ("wrong", "high", "gave up: 'unable to access config.json'"),
    "c73bdceeac3b": (
        "correct",
        "high",
        "flags 70000 out of range, writes corrected config with valid port",
    ),
    # ── GEN-L3-constraint-solve-13 (earliest >=4 = 09:00; p1,p2,p3,p4) ──
    "f6245521e7f6": (
        "wrong",
        "high",
        "hallucination: prod-bug debugging request, off task",
    ),
    "d0460cfdfb1d": ("wrong", "high", "gave up: cannot locate schedule files"),
    "65a8a560b53e": (
        "correct",
        "high",
        "09:00 chosen as earliest >=4 (p1,p2,p3,p4); tie with 11:00 noted",
    ),
    "c627126e6290": (
        "partial",
        "low",
        "09:00 with p1,p2,p3,p4 correct, but threshold framed as >=3 and didn't pick earliest >=4 explicitly",
    ),
    "8f97dffacc8c": (
        "correct",
        "high",
        "09:00 earliest, attendees p1,p2,p3,p4, p5 absent — correct",
    ),
    "0d11f2f8cfb9": ("wrong", "high", "gave up: 'do not have access to file contents'"),
    # ── GEN-L3-iterative-refine-15 (food over 30; cuts total 30, no <actual) ──
    "c6e723bef1c0": (
        "wrong",
        "high",
        "hallucination: Maclaurin series request, off task",
    ),
    "80038f2060d6": (
        "partial",
        "low",
        "correct variances (food +30) but stops at analysis; no offsetting cut proposal",
    ),
    "dd48eda694c7": (
        "partial",
        "low",
        "correct variances but frames as 'under budget'; no offsetting cut set proposed",
    ),
    "fcfcf3e9be1e": (
        "partial",
        "low",
        "correct per-category overrun/under but no cut proposal that balances to zero",
    ),
    "70ff3369ace2": (
        "correct",
        "high",
        "food over by 30, slack travel 50/office 20 identified, proceeds to cut proposal",
    ),
    "4749c9e23482": (
        "partial",
        "low",
        "overrun 30 + under-budget slack identified, but cut set truncated/not clearly summing to 30",
    ),
    # ── GEN-L3-multi-hop-synthesis-14 (paper-3 cited by 3; citers 1,2,4) ──
    "df252d5175f3": (
        "correct",
        "high",
        "paper-3 cited by 1,2,4; foundational; star topology correct",
    ),
    "712b537a664e": (
        "wrong",
        "high",
        "names Paper 2 as the answer; most-cited is paper-3 — wrong paper",
    ),
    "503adbb83c55": (
        "correct",
        "high",
        "paper-3 cited by 1,2,4, claim temporal locality — correct",
    ),
    "353eb85190d9": (
        "correct",
        "high",
        "paper-3 cited by 1,2,4, foundational — correct",
    ),
    "3d6637de85f0": (
        "wrong",
        "high",
        "hallucination: 'don't see the dataset', off task",
    ),
    "a14f868d0ca8": (
        "partial",
        "low",
        "claims correct but 'cites: 3' read literally as count, citers not resolved to paper-3",
    ),
}


def main() -> None:
    items = [json.loads(l) for l in BLIND.read_text().splitlines() if l.strip()]
    by_prefix = {it["item_id"][:12]: it["item_id"] for it in items}
    missing = set(by_prefix) - set(LABELS)
    extra = set(LABELS) - set(by_prefix)
    assert not missing, f"unlabeled items: {missing}"
    assert not extra, f"labels for unknown items: {extra}"
    rows = []
    for prefix, full in by_prefix.items():
        verdict, conf, just = LABELS[prefix]
        rows.append(
            {
                "item_id": full,
                "rater": "agent",
                "verdict": verdict,
                "confidence": conf,
                "justification": just,
            }
        )
    OUT.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    from collections import Counter

    print(f"wrote {len(rows)} rater-1 labels -> {OUT}")
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))


if __name__ == "__main__":
    main()
