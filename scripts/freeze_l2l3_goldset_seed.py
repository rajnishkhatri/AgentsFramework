"""Phase 4 — compute agreement, adjudicate, and freeze the L2/L3 seed gold set.

docs/plans/model_ab_l2l3_blind_adjudication.plan.md, Phase 4. Inputs:
  - l2l3_labels_rater1.jsonl        (agent, blind; hashed before key reveal)
  - l2l3_rater2_worksheet.md        (human; inline verdicts = final adjudicated)
  - l2l3_blinding_proof.json        (the pre-reveal rater-1 hash)
  - l2l3_arm_key.sealed.json        (item_id -> {case, arm}; opened ONLY here)
  - l2l3_answer_keys.json           (rubric)

Adjudication rule (user-confirmed 2026-06-25): rater-2 is the tiebreaker on every
disagreement. Since the human worksheet's inline verdicts already encode the
post-truncation-review final calls, the rater-2 verdict IS the adjudicated label.

IAA via services/governance/iaa.py (krippendorff_alpha_nominal + landis_koch_band) —
reused, not hand-rolled. Gate: 3-class alpha >= 0.80 (else the rubric is ambiguous —
revise Phase 1 and re-grade; do NOT ship).

Freezes cache/goaljudge_eval/model_ab_l2l3_goldset_seed.json with a manifest marked
provisional: true. The sealed arm key is read LAST, after blinding is verified, so
each frozen row can carry its (now-revealed) arm for the downstream per-model report.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from services.governance.iaa import krippendorff_alpha_nominal, landis_koch_band

AGENT_ROOT = Path(__file__).resolve().parent.parent
ANSWER_DIR = AGENT_ROOT / "cache" / "model_ab_answer"
RATER1 = ANSWER_DIR / "l2l3_labels_rater1.jsonl"
RATER2_WORKSHEET = ANSWER_DIR / "l2l3_rater2_worksheet.md"
RATER2_LABELS = ANSWER_DIR / "l2l3_labels_rater2.jsonl"
BLINDING_PROOF = ANSWER_DIR / "l2l3_blinding_proof.json"
SEALED_KEY = ANSWER_DIR / "l2l3_arm_key.sealed.json"
BLIND_ITEMS = ANSWER_DIR / "l2l3_blind_items.jsonl"
ALPHA_GATE = 0.80

# Items excluded from the frozen seed AFTER blinding is verified. These are
# data-quality defects (the answer is corrupted at source), not labeling
# judgments — so they are dropped rather than relabeled. Each entry pins the
# full 32-hex item_id + the reason, so the exclusion is auditable.
#
# 70ff3369…  GEN-L3-iterative-refine-15 / deepseek-v4-pro: the model answer is
#   TRUNCATED at source (ends mid-sentence at "office: up", before stating the
#   proposed cuts or the zero-balance verification). The blind raters labeled it
#   "correct" by inferring the unwritten cut from the visible slack (rater-1's own
#   note says "proceeds to cut proposal" — the answer never does). GoalJudge's
#   "fail" was the CORRECT call against the truncated text. Excluded as
#   truncated-at-source; see docs/adr/0003 + docs/adr/decisions.md (2026-06-28).
EXCLUDED_ITEMS: dict[str, str] = {
    "70ff3369ace25c0d8b332e114099f219": "truncated-at-source (answer cut mid-sentence)",
}

OUT = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goldset_seed.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_rater2(worksheet: Path = RATER2_WORKSHEET) -> dict[str, str]:
    """Inline `### item <id>` ... `verdict: <v>` pairs, stopping before the Notes."""
    body = worksheet.read_text().split("## Rater-2 Notes")[0]
    out: dict[str, str] = {}
    cur: str | None = None
    for line in body.splitlines():
        m = re.match(r"### item ([0-9a-f]{32})", line.strip())
        if m:
            cur = m.group(1)
            continue
        mv = re.match(r"verdict:\s*(correct|partial|wrong)\s*$", line.strip(), re.I)
        if mv and cur:
            out[cur] = mv.group(1).lower()
            cur = None
    return out


def main() -> None:
    # 1. Verify blinding BEFORE opening the sealed key.
    proof = json.loads(BLINDING_PROOF.read_text())
    now_hash = _sha256(RATER1)
    if proof["rater1_labels_sha256"] != now_hash:
        raise SystemExit(
            "BLINDING VIOLATED: rater-1 labels changed since the pre-reveal hash."
        )

    # 2. Load both raters' labels.
    r1 = {
        json.loads(l)["item_id"]: json.loads(l)["verdict"]
        for l in RATER1.read_text().splitlines()
        if l.strip()
    }
    r2 = parse_rater2()
    # persist the parsed rater-2 labels (the human's final inline calls).
    RATER2_LABELS.write_text(
        "\n".join(
            json.dumps({"item_id": i, "rater": "human", "verdict": v})
            for i, v in r2.items()
        )
        + "\n"
    )

    assert set(r1) == set(r2), f"rater coverage mismatch: {set(r1) ^ set(r2)}"

    # Drop data-quality exclusions AFTER blinding is verified (the hash above
    # covers the unmodified rater-1 file, so blinding provenance is preserved).
    for excluded in EXCLUDED_ITEMS:
        r1.pop(excluded, None)
        r2.pop(excluded, None)
    n = len(r1)

    # 3. IAA via the repo primitives (reused, not hand-rolled).
    matrix = [[r1[i], r2[i]] for i in r1]
    alpha = krippendorff_alpha_nominal(matrix)
    band = landis_koch_band(alpha)
    agree = sum(1 for i in r1 if r1[i] == r2[i])

    def _bin(v: str) -> str:
        return "correct" if v == "correct" else "not"

    alpha_bin = krippendorff_alpha_nominal([[_bin(r1[i]), _bin(r2[i])] for i in r1])

    if alpha < ALPHA_GATE:
        raise SystemExit(
            f"GATE FAILED: 3-class alpha {alpha:.3f} < {ALPHA_GATE}. The rubric is "
            "ambiguous — revise Phase 1 keys and re-grade; do NOT freeze."
        )

    # 4. Adjudicate: rater-2 is the tiebreaker (user-confirmed). Record which rows
    #    were disagreements so the provenance is auditable.
    disagreements = [i for i in r1 if r1[i] != r2[i]]
    final = {i: r2[i] for i in r1}  # rater-2 wins on every row (== r1 where agree)

    # 5. NOW open the sealed key (blinding already verified) to attach arm identity.
    sealed = json.loads(SEALED_KEY.read_text())
    blind = {
        json.loads(l)["item_id"]: json.loads(l)
        for l in BLIND_ITEMS.read_text().splitlines()
        if l.strip()
    }

    rows = []
    for i in r1:
        meta = sealed[i]
        rows.append(
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

    test_split_sha = hashlib.sha256(
        json.dumps(sorted((r["item_id"], r["adjudicated"]) for r in rows)).encode()
    ).hexdigest()

    manifest = {
        "name": "model_ab_l2l3_goldset_seed",
        "provisional": True,
        "note": (
            f"v0.1 BOOTSTRAP seed — small ({len(rows)} items, 6 arms x 9 L2/L3 "
            "cases minus data-quality exclusions), 2-rater blind-adjudicated. NOT a "
            "calibrated gold set; cannot pass the repo's v1 floor gate. Feeds the "
            "Stage 5/6 calibration pipeline as wave-0 GAIA-shape answer-correctness "
            "rows."
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "excluded_items": EXCLUDED_ITEMS,
        "row_count": len(rows),
        "rater_count": 2,
        "raters": ["agent(blind)", "human(blind)"],
        "adjudication_rule": "rater-2 is tiebreaker (user-confirmed 2026-06-25)",
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
        "blinding": {
            "held": True,
            "rater1_labels_sha256": now_hash,
            "recorded_before_key_reveal_at": proof.get("recorded_at"),
            "evidence": (
                "rater-1 label hash matches the value recorded in "
                "l2l3_blinding_proof.json before l2l3_arm_key.sealed.json was opened"
            ),
        },
        "test_split_sha256": test_split_sha,
        "iaa_source": "services/governance/iaa.py (reused, not hand-rolled)",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"manifest": manifest, "rows": rows}, indent=2) + "\n")

    from collections import Counter

    print(f"FROZEN -> {OUT}")
    print(
        f"  rows: {len(rows)}  alpha(3class): {alpha:.3f} ({band})  "
        f"alpha(binary): {alpha_bin:.3f}"
    )
    print(f"  raw agreement: {agree}/{n}  disagreements: {len(disagreements)}")
    print(f"  adjudicated verdicts: {dict(Counter(r['adjudicated'] for r in rows))}")
    print(f"  blinding held: {manifest['blinding']['held']}")
    print(f"  provisional: {manifest['provisional']}")


if __name__ == "__main__":
    main()
