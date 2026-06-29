"""Harvest the gpt-4o-mini + gpt-5 GROWTH arms (cases 16-24) — UNCLIPPED + judged.

docs/plans/model_ab_l2l3_blind_adjudication.plan.md, growth wave. The original 4
growth arms were harvested via the model-A/B `call_llm` records, whose `ai_response`
is PRE-CLIPPED to 500 chars (orchestration/react_loop.py:2220) — that clip produced
the 18 truncated-at-source answers the full-88 gate had to exclude. This runner
avoids that defect two ways:

  * It drives each (gpt arm x case) through the REAL compiled graph with GoalJudge
    ENABLED (run_goaljudge_synthetic_batch.run_case + build_agent_and_tools, which
    sets goal_judge_enabled=True), so a `goal_judge` evals.log record is emitted.
  * It reads the answer from that record's `ai_input.final_answer` — clipped at
    8192 chars (eval_telemetry.clip_eval_text), the SAME view the live judge graded,
    not the 500-char call_llm clip. So these answers are faithful re-judge inputs.

As a bonus the GoalJudge verdict is captured in the same pass (no reconstructed
evidence needed, unlike scripts/run_growth_goaljudge.py for the other arms).

SEPARATE NAMESPACE: writes l2l3_growth_gpt_* files only. It NEVER touches the
shared l2l3_growth_{raw_answers,blind_items,arm_key.sealed} files — a parallel
session is mid-flight growing those to a 5th (glm-5.1) arm; the gpt arms merge in
only at the freeze step, once both waves are blind-graded.

Live LLM (cadence/pre-swap, attended — never CI). Model pinned via the input
`selected_model` key (the router's pinned_model branch), MODEL_PROFILE_SET=all so
the gpt profiles register.

Outputs (cache/model_ab_answer/):
  l2l3_growth_gpt_raw_answers.json    {arm: {case: unclipped_answer}}
  l2l3_growth_gpt_goaljudge_verdicts.json
      {synthetic_item_id: {case, arm, goal_met, criteria_met, rationale, verifier_source}}
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT / "scripts"))
load_dotenv(AGENT_ROOT / ".env")
os.environ["MODEL_PROFILE_SET"] = "all"  # register the gpt profiles for pinning

from tests.fixtures.goaljudge.case_registry import GoalJudgeCase  # noqa: E402

from scripts.run_goaljudge_synthetic_batch import (  # noqa: E402
    build_agent_and_tools,
    run_case,
    truncate_eval_log,
)

# GoalJudge / eval-capture writes here (fixed path, NOT a per-arm dir or env var);
# truncate_eval_log() clears it. We truncate between arms for clean last-wins reads.
EVAL_LOG = AGENT_ROOT / "logs" / "evals.log"

AD = AGENT_ROOT / "cache" / "model_ab_answer"
WORKSPACE = AGENT_ROOT / "workspace"
BATCH = AD / "l2l3_growth_batch.jsonl"
RUN_ROOT = AGENT_ROOT / "cache" / "model_ab" / "l2l3_growth_gpt"

OUT_ANSWERS = AD / "l2l3_growth_gpt_raw_answers.json"
OUT_VERDICTS = AD / "l2l3_growth_gpt_goaljudge_verdicts.json"

# gpt-5 only: gpt-4o-mini is flaky in the tool-calling ReAct loop (empty tool-call
# turns that derail the run before final-answer synthesis — confirmed by a smoke
# producing 7 empty call_llm turns; base-wave content rate was 12/52 vs opus 33/38).
# gpt-5 (capable tier) reaches a clean final answer + GoalJudge record. Decision:
# harvest gpt-5 only (+9 rows -> 97); gpt-4o-mini deferred pending a loop-flakiness fix.
ARMS = ["gpt-5"]


def _load_cases() -> list[GoalJudgeCase]:
    """The 9 growth cases as GoalJudgeCase objects (prompt-only; the verdict comes
    from the live judge, target_code is unused here)."""
    cases: list[GoalJudgeCase] = []
    for line in BATCH.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        cases.append(
            GoalJudgeCase(
                id=r["case"],
                prompt=r["prompt"],
                target_code="N/A",
                target_axes=[],
                stratum="L2L3-growth",
                domain="general",
                expected_feasibility="feasible",
                provenance="l2l3_growth_batch",
            )
        )
    return cases


def _read_goal_judge_record(eval_log: Path, case_id: str) -> dict | None:
    """Last `goal_judge` record for a case (keyed by uuid5(case)), unclipped view."""
    tid = uuid.uuid5(uuid.NAMESPACE_DNS, case_id).hex
    found: dict | None = None
    if not eval_log.exists():
        return None
    for line in eval_log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("target") == "goal_judge" and rec.get("task_id") == tid:
            found = rec  # last wins
    return found


async def main() -> None:
    cases = _load_cases()
    cfg, routing, tools, facts = build_agent_and_tools()

    answers: dict[str, dict[str, str]] = {a: {} for a in ARMS}
    verdicts: dict[str, dict] = {}

    for arm in ARMS:
        arm_dir = RUN_ROOT / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        # The goal_judge record lands in logs/evals.log (fixed path). Truncate it
        # before each arm so the per-case last-wins read sees only THIS arm.
        truncate_eval_log()
        eval_log = EVAL_LOG

        for case in cases:
            await run_case(
                case,
                cfg,
                routing,
                tools,
                facts,
                workspace=WORKSPACE,
                cache_dir=arm_dir,
                graph_input_extra={"selected_model": arm},
            )
            rec = _read_goal_judge_record(eval_log, case.id)
            if rec is None:
                print(f"  !! {arm} {case.id}: NO goal_judge record")
                continue
            ai_in = rec.get("ai_input") or {}
            ans = str(ai_in.get("final_answer", ""))
            resp = rec.get("ai_response") or {}
            answers[arm][case.id] = ans
            item_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{arm}:{case.id}").hex
            verdicts[item_id] = {
                "case": case.id,
                "arm": arm,
                "goal_met": bool(resp.get("goal_met")),
                "criteria_met": resp.get("criteria_met"),
                "rationale": str(resp.get("rationale", "")),
                "verifier_source": resp.get("verifier_source"),
                "answer_len": len(ans),
            }
            met = resp.get("goal_met")
            src = resp.get("verifier_source") or "llm"
            print(f"  {arm:12s} {case.id:34s} met={met} len={len(ans)} [{src}]")

    OUT_ANSWERS.write_text(json.dumps(answers, indent=2) + "\n")
    OUT_VERDICTS.write_text(json.dumps(verdicts, indent=2) + "\n")
    n = sum(len(v) for v in answers.values())
    met = sum(1 for v in verdicts.values() if v["goal_met"])
    clipped = sum(1 for v in verdicts.values() if v["answer_len"] >= 8000)
    print(f"\nharvested {n} gpt growth answers -> {OUT_ANSWERS}")
    print(f"  verdicts -> {OUT_VERDICTS}  (goal_met True: {met} / False: {n - met})")
    print(f"  answers at/over 8000 chars (near the 8192 clip): {clipped}")


if __name__ == "__main__":
    asyncio.run(main())
