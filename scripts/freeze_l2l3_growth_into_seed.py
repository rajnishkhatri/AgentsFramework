"""Append the Wave-1 GROWTH rows (4 arms x cases 16-24) to the frozen L2/L3 seed.

docs/plans/model_ab_l2l3_blind_adjudication.plan.md Phase 4, growth wave. The base
seed (cache/goaljudge_eval/model_ab_l2l3_goldset_seed.json, 52 rows, cases 07-15)
was frozen earlier; this grows it with the 36 independently blind-adjudicated growth
items. The growth batch has its OWN blinding proof (hashes the BLIND ITEMS, not the
rater-1 labels — a stronger guarantee), so this script verifies that hash before
opening the sealed arm key, then attaches arm identity and appends.

Gate (same as base): 3-class Krippendorff alpha >= 0.80 over the growth pairs, via
services/governance/iaa.py (reused, not hand-rolled). Two raters graded blind and
INDEPENDENTLY; rater-2 (human) is the tiebreaker, matching the base adjudication rule.

Idempotent: re-running replaces the growth rows (matched by case 16-24) rather than
duplicating them. Writes a .bak of the prior seed once.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from services.governance.iaa import krippendorff_alpha_nominal, landis_koch_band

AGENT_ROOT = Path(__file__).resolve().parent.parent
AD = AGENT_ROOT / "cache" / "model_ab_answer"
SEED = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goldset_seed.json"

BLIND_ITEMS = AD / "l2l3_growth_blind_items.jsonl"
BLINDING_PROOF = AD / "l2l3_growth_blinding_proof.json"
SEALED_KEY = AD / "l2l3_growth_arm_key.sealed.json"
RATER1 = AD / "l2l3_growth_labels_rater1.jsonl"
ANSWERED_WORKSHEET = AD / "l2l3_growth_rater_worksheet_detailed_answered.md"

ALPHA_GATE = 0.80
GROWTH_CASE_RE = re.compile(r"-(1[6-9]|2[0-4])$")  # cases 16-24


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_rater2(worksheet: Path) -> dict[str, str]:
    """Extract `#### Item <id>` -> the following `**Verdict:** <label>` from the
    answered detailed worksheet (the human's final inline calls)."""
    out: dict[str, str] = {}
    cur: str | None = None
    item_re = re.compile(r"^#### Item `([0-9a-f]{32})`")
    verdict_re = re.compile(r"^\*\*Verdict:\*\* `(correct|partial|wrong)`")
    for line in worksheet.read_text().splitlines():
        m = item_re.match(line)
        if m:
            cur = m.group(1)
            continue
        v = verdict_re.match(line)
        if v and cur:
            out[cur] = v.group(1)
            cur = None
    return out


def main() -> None:
    # 1. Verify GROWTH blinding BEFORE opening the sealed key: the blind-items file
    #    must hash to the value sealed at build time (proves the items the raters saw
    #    are exactly what was sealed — no post-hoc tampering).
    proof = json.loads(BLINDING_PROOF.read_text())
    now_hash = _sha256_bytes(BLIND_ITEMS.read_bytes())
    if proof["blind_items_sha256"] != now_hash:
        raise SystemExit(
            "BLINDING VIOLATED: growth blind-items hash != sealed proof; abort freeze."
        )

    # 2. Load both raters' labels (rater-1 from the jsonl, rater-2 from the answered
    #    detailed worksheet).
    r1 = {
        json.loads(l)["item_id"]: json.loads(l)["label"]
        for l in RATER1.read_text().splitlines()
        if l.strip()
    }
    r2 = parse_rater2(ANSWERED_WORKSHEET)
    assert set(r1) == set(r2), f"rater coverage mismatch: {set(r1) ^ set(r2)}"
    n = len(r1)

    # 3. IAA via repo primitives.
    matrix = [[r1[i], r2[i]] for i in r1]
    alpha = krippendorff_alpha_nominal(matrix)
    band = landis_koch_band(alpha)
    agree = sum(1 for i in r1 if r1[i] == r2[i])

    def _bin(v: str) -> str:
        return "correct" if v == "correct" else "not"

    alpha_bin = krippendorff_alpha_nominal([[_bin(r1[i]), _bin(r2[i])] for i in r1])

    if alpha < ALPHA_GATE:
        raise SystemExit(
            f"GATE FAILED: growth 3-class alpha {alpha:.3f} < {ALPHA_GATE}; do NOT freeze."
        )

    # 4. Adjudicate: rater-2 is the tiebreaker (== r1 where they agree).
    disagreements = [i for i in r1 if r1[i] != r2[i]]
    final = {i: r2[i] for i in r1}

    # 5. Open the sealed key (blinding verified) and build growth rows.
    sealed = json.loads(SEALED_KEY.read_text())
    growth_rows = []
    for i in r1:
        meta = sealed[i]
        growth_rows.append(
            {
                "item_id": i,
                "case": meta["case"],
                "arm": meta["arm"],
                "rater1": r1[i],
                "rater2": r2[i],
                "adjudicated": final[i],
                "was_disagreement": i in disagreements,
            }
        )

    # 6. Load the base seed, drop any prior growth rows (idempotent), append.
    seed = json.loads(SEED.read_text())
    base_rows = [r for r in seed["rows"] if not GROWTH_CASE_RE.search(r["case"])]
    dropped = len(seed["rows"]) - len(base_rows)
    if dropped:
        print(f"  (replacing {dropped} prior growth rows)")
    SEED.with_suffix(".json.bak").write_text(json.dumps(seed, indent=2) + "\n")

    rows = base_rows + growth_rows
    test_split_sha = hashlib.sha256(
        json.dumps(sorted((r["item_id"], r["adjudicated"]) for r in rows)).encode()
    ).hexdigest()

    m = seed["manifest"]
    m["row_count"] = len(rows)
    m["created_at"] = datetime.now(timezone.utc).isoformat()
    m["test_split_sha256"] = test_split_sha
    m["note"] = (
        f"v0.2 BOOTSTRAP seed — {len(rows)} items (base cases 07-15 + growth cases "
        "16-24, 4 live arms: opus/haiku/deepseek-pro/deepseek-flash; gpt-4o-mini + "
        "gpt-5 growth arms DEFERRED on OpenAI quota). 2-rater blind-adjudicated. NOT "
        "a calibrated gold set; feeds Stage 5/6 calibration as answer-correctness rows."
    )
    m["growth_wave"] = {
        "added_rows": len(growth_rows),
        "cases": sorted({r["case"] for r in growth_rows}),
        "arms": sorted({r["arm"] for r in growth_rows}),
        "raters": ["agent(blind)", "human(blind)"],
        "adjudication_rule": "rater-2 is tiebreaker (matches base)",
        "agreement": {
            "raw_3class": round(agree / n, 4),
            "krippendorff_alpha_3class": round(alpha, 4),
            "alpha_band_3class": band,
            "krippendorff_alpha_binary_correct_vs_not": round(alpha_bin, 4),
            "n_items": n,
            "n_disagreements": len(disagreements),
            "disagreement_item_ids": disagreements,
        },
        "alpha_gate": ALPHA_GATE,
        "caveat": (
            "alpha=1.0 reflects a 2-class outcome distribution (correct/partial; "
            "0 'wrong'), so the disagreement space was narrower than the base wave's "
            "3-class grade. Agreement is genuine but less stress-tested across classes."
        ),
        "blinding": {
            "held": True,
            "blind_items_sha256": now_hash,
            "evidence": (
                "growth blind-items hash matches l2l3_growth_blinding_proof.json "
                "recorded before l2l3_growth_arm_key.sealed.json was opened"
            ),
        },
        "deferred": {
            "missing_arms": ["gpt-4o-mini", "gpt-5"],
            "reason": "OpenAI quota exhausted (429 insufficient_quota) at harvest time",
            "to_reach": "108 rows once OpenAI is topped up and the 2 arms re-harvested",
        },
    }

    seed["rows"] = rows
    SEED.write_text(json.dumps({"manifest": m, "rows": rows}, indent=2) + "\n")

    from collections import Counter

    print(f"FROZEN -> {SEED}")
    print(
        f"  total rows: {len(rows)}  (base {len(base_rows)} + growth {len(growth_rows)})"
    )
    print(
        f"  growth alpha(3class): {alpha:.3f} ({band})  alpha(binary): {alpha_bin:.3f}"
    )
    print(f"  growth raw agreement: {agree}/{n}  disagreements: {len(disagreements)}")
    print(
        f"  growth adjudicated: {dict(Counter(r['adjudicated'] for r in growth_rows))}"
    )
    print(f"  full-seed adjudicated: {dict(Counter(r['adjudicated'] for r in rows))}")
    print(f"  provisional: {m['provisional']}")


if __name__ == "__main__":
    main()
