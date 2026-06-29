"""Build the BLINDED GROWTH L2/L3 adjudication set (cases 16-24).

The growth-wave sibling of ``build_l2l3_blind_set.py``. Same blinding contract —
one anonymized item per (case x arm) with NO model/arm identifier, shuffled with
the fixed seed 1729 so re-runs are reproducible, and the arm<->item_id mapping
sealed in a separate file opened only after grading is frozen.

Reuses ``build_l2l3_blind_set.build_blind_set`` (the same item_id derivation
``uuid5(case|arm|text)`` and shuffle) so the 4 original arms' 36 item_ids stay
STABLE when a new arm is added — only the new arm's item_ids append. Existing
rater-1 labels and rater-2 verdicts (keyed by item_id) therefore remain valid.

Adds the blinding-proof hash the growth freeze (``freeze_l2l3_growth_into_seed``)
verifies before opening the sealed key — a tamper-evidence record that the blind
items the raters saw are exactly what was sealed.

Inputs:
  - cache/model_ab_answer/l2l3_growth_raw_answers.json  ({arm: {case: answer}})
  - cache/model_ab_answer/l2l3_growth_batch.jsonl        (case -> prompt)
  - cache/model_ab_answer/l2l3_answer_keys.json          (case -> rubric facts)

Outputs:
  - cache/model_ab_answer/l2l3_growth_blind_items.jsonl      (NO arm info)
  - cache/model_ab_answer/l2l3_growth_arm_key.sealed.json    (item_id -> {case, arm})
  - cache/model_ab_answer/l2l3_growth_blinding_proof.json    ({blind_items_sha256, ...})
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.build_l2l3_blind_set import build_blind_set, leak_scan

AGENT_ROOT = Path(__file__).resolve().parent.parent
AD = AGENT_ROOT / "cache" / "model_ab_answer"
RAW = AD / "l2l3_growth_raw_answers.json"
BATCH = AD / "l2l3_growth_batch.jsonl"
KEYS = AD / "l2l3_answer_keys.json"
BLIND_OUT = AD / "l2l3_growth_blind_items.jsonl"
SEALED_OUT = AD / "l2l3_growth_arm_key.sealed.json"
PROOF_OUT = AD / "l2l3_growth_blinding_proof.json"


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> None:
    items, sealed, skipped = build_blind_set(raw=RAW, batch=BATCH, keys=KEYS, seed=1729)
    BLIND_OUT.write_text("\n".join(json.dumps(it) for it in items) + "\n")
    SEALED_OUT.write_text(json.dumps(sealed, indent=2) + "\n")

    proof = {
        "blind_items_sha256": _sha256_bytes(BLIND_OUT.read_bytes()),
        "n_items": len(items),
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "fixtures_seeded": True,
        "note": "sealed arm key opened ONLY after rater labels frozen",
    }
    PROOF_OUT.write_text(json.dumps(proof, indent=2) + "\n")

    arms = sorted({v["arm"] for v in sealed.values()})
    print(f"wrote {len(items)} blind items -> {BLIND_OUT}")
    print(f"wrote sealed key ({len(sealed)} ids, arms={arms}) -> {SEALED_OUT}")
    print(f"wrote blinding proof -> {PROOF_OUT}")
    if skipped:
        print(f"SKIPPED (empty answer) {len(skipped)}:")
        for arm, case in skipped:
            print(f"  {arm}  {case}")
    leaks = leak_scan(items)
    if leaks:
        print(f"LEAK WARNING: arm tokens in structural fields ({len(leaks)}):")
        for iid, tok in leaks[:10]:
            print(f"  {iid}  '{tok}'")
    else:
        print("blinding OK: no arm tokens in structural fields")


if __name__ == "__main__":
    main()
