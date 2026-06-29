"""Overlay the deterministic answer-verifier cascade onto the harvested L2/L3
GoalJudge verdicts — offline, zero live-LLM cost.

Why this exists: ``cache/model_ab_answer/l2l3_goaljudge_verdicts.json`` was
harvested from each arm's ``evals.log`` *before* the correctness cascade
(``components/answer_verifiers.py``, commit 463ac59) was added to GoalJudge.
Those verdicts are LLM-rubric-only and contain the known process-not-correctness
errors (e.g. a REVERSED topological sort scored ``goal_met=true``). Re-running the
full judge would invoke the LLM on the abstained shapes (live cost). Instead, this
script reproduces exactly what ``components/goal_judge.py``'s cascade does at
runtime — the deterministic verifier owns the verdict on a checkable shape, and
the existing LLM verdict is kept verbatim wherever the verifier abstains.

Contract (mirrors GoalJudge.evaluate, components/goal_judge.py:107):
  verified = verify_answer(task_input, final_answer, evidence)
  - bool  -> override goal_met; criteria_met = 1.0/0.0; verifier_source="deterministic"
  - None  -> keep the harvested LLM verdict unchanged (verifier_source=None)

Inputs:
  cache/model_ab_answer/l2l3_goaljudge_verdicts.json   (harvested LLM verdicts)
  cache/goaljudge_eval/model_ab_l2l3_goldset_seed.json (the frozen rows)
  cache/model_ab_answer/l2l3_raw_answers.json          (arm -> case -> answer)
  cache/model_ab_answer/l2l3_blind_items.jsonl + l2l3_arm_key.sealed.json (case -> prompt)

Output:
  cache/model_ab_answer/l2l3_goaljudge_verdicts_cascade.json
"""

from __future__ import annotations

import json
from pathlib import Path

from components.answer_verifiers import verify_answer

AGENT_ROOT = Path(__file__).resolve().parent.parent
ANSWER_DIR = AGENT_ROOT / "cache" / "model_ab_answer"
SEED = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goldset_seed.json"
HARVESTED = ANSWER_DIR / "l2l3_goaljudge_verdicts.json"
RAW_ANSWERS = ANSWER_DIR / "l2l3_raw_answers.json"
BLIND_ITEMS = ANSWER_DIR / "l2l3_blind_items.jsonl"
SEALED_KEY = ANSWER_DIR / "l2l3_arm_key.sealed.json"
OUT = ANSWER_DIR / "l2l3_goaljudge_verdicts_cascade.json"


def _case_prompts() -> dict[str, str]:
    """case -> task prompt, recovered from the (un-sealed) blind items."""
    sealed = json.loads(SEALED_KEY.read_text())
    out: dict[str, str] = {}
    for line in BLIND_ITEMS.read_text().splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        case = sealed.get(item["item_id"], {}).get("case")
        if case and case not in out:
            out[case] = item["prompt"]
    return out


def main() -> None:
    harvested = json.loads(HARVESTED.read_text())
    seed = json.loads(SEED.read_text())
    raw = json.loads(RAW_ANSWERS.read_text())
    case_prompt = _case_prompts()

    out: dict[str, dict] = {}
    flips: list[tuple[str, str, str, bool, bool]] = []
    n_det = 0
    for row in seed["rows"]:
        item_id = row["item_id"]
        case, arm = row["case"], row["arm"]
        base = harvested.get(item_id)
        if base is None:
            # No harvested verdict to overlay; skip (stays out of validation).
            continue
        prompt = case_prompt.get(case)
        answer = raw.get(arm, {}).get(case)
        verdict = dict(base)
        verdict["verifier_source"] = None
        if prompt is not None and answer is not None:
            verified = verify_answer(prompt, answer, evidence=None)
            if verified is not None:
                n_det += 1
                if bool(base.get("goal_met")) != verified:
                    flips.append(
                        (item_id[:8], case, arm, bool(base.get("goal_met")), verified)
                    )
                verdict["goal_met"] = verified
                verdict["criteria_met"] = 1.0 if verified else 0.0
                verdict["verifier_source"] = "deterministic"
                verdict["rationale"] = (
                    "Deterministic verifier: the produced result "
                    + ("satisfies" if verified else "violates")
                    + " the task's stated constraints."
                )
        out[item_id] = verdict

    OUT.write_text(json.dumps(out, indent=2) + "\n")
    met = sum(1 for v in out.values() if v["goal_met"])
    print(f"cascade-applied {len(out)} verdicts -> {OUT}")
    print(
        f"  deterministic verdicts: {n_det}  goal_met True: {met}  False: {len(out) - met}"
    )
    if flips:
        print(f"  verifier FLIPPED {len(flips)} verdict(s) (LLM -> deterministic):")
        for short, case, arm, was, now in flips:
            print(f"    {short}  {case} / {arm}: goal_met {was} -> {now}")
    else:
        print("  no flips (verifier agreed with every harvested verdict it graded)")


if __name__ == "__main__":
    main()
