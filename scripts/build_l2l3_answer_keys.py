"""Emit the L2/L3 rubric answer keys from the seeder's ground truth.

Phase 1 of the blind-adjudication plan (docs/plans/
model_ab_l2l3_blind_adjudication.plan.md). The keys are NOT authored here — they are
projected from ``GROUND_TRUTH`` in seed_model_ab_l2l3_workspace.py, the single source
of truth that also writes the fixtures. Keeping the rubric and the fixtures in one
place means a correct answer is always derivable from the seeded files alone, and the
rubric can never drift from what was seeded.

Output: cache/model_ab_answer/l2l3_answer_keys.json — ``{case: {must_have_facts,
acceptable_variation}}``. Idempotent.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.seed_model_ab_l2l3_workspace import GROUND_TRUTH

AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = AGENT_ROOT / "cache" / "model_ab_answer" / "l2l3_answer_keys.json"


def build_keys() -> dict[str, dict[str, list[str]]]:
    return {
        g.case: {
            "must_have_facts": list(g.facts),
            "acceptable_variation": list(g.notes),
        }
        for g in GROUND_TRUTH
    }


def write_json(keys: dict[str, dict[str, list[str]]], out: Path = DEFAULT_OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(keys, indent=2) + "\n")
    return out


if __name__ == "__main__":
    keys = build_keys()
    write_json(keys)
    print(f"wrote {len(keys)} rubric keys -> {DEFAULT_OUT}")
    for case, k in keys.items():
        print(f"  {case} ({len(k['must_have_facts'])} facts)")
