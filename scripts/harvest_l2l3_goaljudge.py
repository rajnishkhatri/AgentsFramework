"""Harvest GoalJudge verdicts for the 53 frozen-seed L2/L3 items.

docs/plans (GoalJudge-vs-seed measurement), Step 1. For every row of the frozen
seed (item_id -> case, arm), pull the automated GoalJudge verdict (goal_met +
criteria_met) from that arm's per-arm evals.log, so we can measure the judge against
the human-adjudicated gold labels. Pure offline — GoalJudge already ran on every
L2/L3 case in all 6 seeded runs.

Reuses, does not re-implement:
  - scripts.model_ab_answer_score._goal_judge_by_case — verdict extraction (last-wins,
    keyed by uuid5(case)).
  - scripts.harvest_l2l3_answers.DEFAULT_SOURCES — the arm -> (run_dir, sub) map.

Output: cache/model_ab_answer/l2l3_goaljudge_verdicts.json —
  {item_id: {case, arm, goal_met, criteria_met}}.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.harvest_l2l3_answers import DEFAULT_SOURCES
from scripts.model_ab_answer_score import _goal_judge_by_case

AGENT_ROOT = Path(__file__).resolve().parent.parent
MODEL_AB = AGENT_ROOT / "cache" / "model_ab"
SEED = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goldset_seed.json"
OUT = AGENT_ROOT / "cache" / "model_ab_answer" / "l2l3_goaljudge_verdicts.json"


def harvest_goaljudge(
    seed_path: Path = SEED,
    sources: dict[str, tuple[str, str]] = DEFAULT_SOURCES,
    model_ab: Path = MODEL_AB,
) -> tuple[dict[str, dict], list[str]]:
    """Return ({item_id: {case, arm, goal_met, criteria_met}}, missing_item_ids)."""
    seed = json.loads(seed_path.read_text())
    rows = seed["rows"]

    # Group the seed's cases by arm so we read each arm's evals.log once.
    cases_by_arm: dict[str, list[str]] = {}
    for r in rows:
        cases_by_arm.setdefault(r["arm"], []).append(r["case"])

    # Per arm: case -> GoalJudge ai_response dict.
    judged_by_arm: dict[str, dict[str, dict]] = {}
    for arm, cases in cases_by_arm.items():
        run_dir, sub = sources[arm]
        eval_log = model_ab / run_dir / sub / "evals.log"
        judged_by_arm[arm] = (
            _goal_judge_by_case(eval_log, cases) if eval_log.exists() else {}
        )

    out: dict[str, dict] = {}
    missing: list[str] = []
    for r in rows:
        verdict = judged_by_arm.get(r["arm"], {}).get(r["case"])
        if verdict is None:
            missing.append(r["item_id"])
            continue
        out[r["item_id"]] = {
            "case": r["case"],
            "arm": r["arm"],
            "goal_met": bool(verdict.get("goal_met")),
            "criteria_met": verdict.get("criteria_met"),
            "rationale": str(verdict.get("rationale", "")),
        }
    return out, missing


def write_json(verdicts: dict[str, dict], out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdicts, indent=2) + "\n")
    return out


if __name__ == "__main__":
    verdicts, missing = harvest_goaljudge()
    write_json(verdicts)
    print(f"harvested {len(verdicts)} GoalJudge verdicts -> {OUT}")
    met = sum(1 for v in verdicts.values() if v["goal_met"])
    print(f"  goal_met True: {met}  False: {len(verdicts) - met}")
    if missing:
        print(f"MISSING ({len(missing)}):")
        for i in missing:
            print(f"  {i[:12]}")
    else:
        print("all seed items have a GoalJudge verdict")
