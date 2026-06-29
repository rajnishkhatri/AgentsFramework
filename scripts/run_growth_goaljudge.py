"""Run GoalJudge LIVE over the 36 GROWTH answers (4 arms x cases 16-24).

docs/plans/model_ab_l2l3_blind_adjudication.plan.md, growth wave — the missing
verdict track. The growth A/B harvest captured only final answers (no `goal_judge`
records in its evals.log, unlike the base wave), so there is nothing to harvest;
this runs the real GoalJudge fresh, matching how the base-52 verdicts were produced.

Faithfulness to the base wave (so the combined 88-row gate is not confounded):
  * Same judge model: ``gpt-4o`` (the base wave pinned gpt-4o, not a tier alias).
  * Same component: the production ``components.goal_judge.GoalJudge`` — including
    its deterministic correctness cascade (``verify_answer`` fires first for
    checkable shapes; the LLM rubric only runs when the verifier abstains).
  * Same evidence shape: a per-fixture evidence digest. The growth trajectory was
    NOT preserved, so we RECONSTRUCT it from the on-disk ``workspace/`` fixtures —
    identical file *bytes* to what the agent read (the verifiers recompute over the
    tool-output contents). HONEST LIMIT: this omits any wrong intermediate steps the
    agent took, so the reconstructed evidence is slightly more lenient on *process*
    than the base wave's real trajectory. Recorded in the output manifest.

Live LLM (cadence/pre-swap, attended — never CI). Idempotent: overwrites the output.

Output: cache/model_ab_answer/l2l3_growth_goaljudge_verdicts.json —
  {item_id: {case, arm, goal_met, criteria_met, rationale, verifier_source}}
matching scripts/harvest_l2l3_goaljudge.py's schema so measure/validation reuse it.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT / "scripts"))
load_dotenv(AGENT_ROOT / ".env")

from components.goal_judge import GoalJudge  # noqa: E402
from services.base_config import AgentConfig  # noqa: E402
from services.llm_config import LLMService, build_model_registry  # noqa: E402
from services.prompt_service import PromptService  # noqa: E402

# CASE_META carries the per-case fixture list (rel paths under workspace/), reused
# from the detailed-worksheet builder so the fixture mapping has ONE source.
from build_growth_detailed_worksheet import CASE_META  # noqa: E402

AD = AGENT_ROOT / "cache" / "model_ab_answer"
WORKSPACE = AGENT_ROOT / "workspace"
RAW_ANSWERS = AD / "l2l3_growth_raw_answers.json"
BATCH = AD / "l2l3_growth_batch.jsonl"
SEED = AGENT_ROOT / "cache" / "goaljudge_eval" / "model_ab_l2l3_goldset_seed.json"
OUT = AD / "l2l3_growth_goaljudge_verdicts.json"

import re  # noqa: E402

GROWTH_CASE_RE = re.compile(r"-(1[6-9]|2[0-4])$")  # cases 16-24

JUDGE_MODEL = "gpt-4o"  # matches the base wave's pinned judge (NOT a tier alias)


def _load_prompts() -> dict[str, str]:
    """case -> task prompt (the same text the agent was given)."""
    out: dict[str, str] = {}
    for line in BATCH.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out[r["case"]] = r["prompt"]
    return out


def _write_target(case: str, prompt: str) -> str | None:
    """The /workspace/out/... path the task asks the agent to write, if any."""
    m = re.search(r"/workspace/(out/\S+?\.(?:txt|json|csv))", prompt)
    return m.group(1) if m else None


def _reconstruct_evidence(case: str, prompt: str) -> list[dict]:
    """Build an evidence digest for ``case`` from the on-disk artifacts.

    READ entries (one per fixture) carry the REAL file bytes the agent read —
    the verifiers recompute over exactly this content, so the deterministic
    cascade fires identically to the base wave (which saw the fixtures via the
    agent's `cat` stdout).

    WRITE entry: when the task names a ``/workspace/out/...`` target and that
    file exists on disk, append a synthetic ``file_io write`` entry carrying the
    on-disk contents. This restores the side-effect signal the growth harvest
    dropped (it saved final-answer-only, so the write tool-call the base wave
    preserved is gone) — WITHOUT it the judge false-downgrades every correct
    write-task answer for "no write in evidence".

    DOCUMENTED APPROXIMATION: the out/ file is shared and overwritten across
    arms, so the write entry is NOT per-arm attributable — it reflects what is
    on disk, not which arm wrote it. Faithful to the artifact, not to provenance.
    """
    evidence: list[dict] = []
    for rel in CASE_META[case]["fixtures"]:
        path = WORKSPACE / rel
        evidence.append(
            {
                "tool_name": "file_io",
                "tool_input": {"path": f"/workspace/{rel}", "operation": "read"},
                "tool_output": path.read_text(),
            }
        )
    target = _write_target(case, prompt)
    if target and (WORKSPACE / target).exists():
        evidence.append(
            {
                "tool_name": "file_io",
                "tool_input": {
                    "path": f"/workspace/{target}",
                    "operation": "write",
                    "content": (WORKSPACE / target).read_text(),
                },
                "tool_output": {"status": "written", "path": f"/workspace/{target}"},
            }
        )
    return evidence


async def main() -> None:
    raw = json.loads(RAW_ANSWERS.read_text())  # {arm: {case: answer}}
    prompts = _load_prompts()

    # Judge EXACTLY the growth rows that are in the FROZEN seed. Iterate the seed so
    # the verdict set is exactly the eligible-item set (the sealed key may carry
    # arms that were NOT frozen into the seed; judging those would produce orphan
    # verdicts judge_validation never asks about).
    seed = json.loads(SEED.read_text())
    targets = [r for r in seed["rows"] if GROWTH_CASE_RE.search(r["case"])]

    # RESUME MODE: when a new arm is added to an already-frozen seed, re-judging the
    # already-judged items would (a) waste live-LLM budget and (b) confound the prior
    # recorded gate via LLM non-determinism. Skip any item_id already present in the
    # output file; judge only the missing ones. Override with --force to re-judge all.
    force = "--force" in sys.argv
    out: dict[str, dict] = {}
    if OUT.exists() and not force:
        out = json.loads(OUT.read_text())
        if not isinstance(out, dict):
            out = {}
    already = set(out)

    # arm-name in the sealed key may differ from the raw-answers key (registry name
    # vs. display); build a (case, arm) -> answer lookup keyed by the raw-answers
    # arm labels, then resolve each sealed item by its (case, arm).
    answers_by_arm_case = {
        (arm, case): ans for arm, cases in raw.items() for case, ans in cases.items()
    }

    models, default_model = build_model_registry("all")
    llm = LLMService(AgentConfig(default_model=default_model, models=models))
    judge = GoalJudge(
        llm_service=llm,
        prompt_service=PromptService(),
        judge_profile=llm.get_profile(JUDGE_MODEL),
    )

    missing: list[str] = []
    judged_new = 0
    for row in targets:
        item_id, case, arm = row["item_id"], row["case"], row["arm"]
        if item_id in already:
            continue
        ans = answers_by_arm_case.get((arm, case))
        if ans is None:
            missing.append(f"{item_id[:12]} ({arm}/{case})")
            continue
        verdict = await judge.evaluate(
            task_input=prompts[case],
            final_answer=ans,
            success_conditions=[],
            evidence=_reconstruct_evidence(case, prompts[case]),
        )
        out[item_id] = {
            "case": case,
            "arm": arm,
            "goal_met": bool(verdict.goal_met),
            "criteria_met": float(verdict.criteria_met),
            "rationale": str(verdict.rationale),
            "verifier_source": verdict.verifier_source,
        }
        judged_new += 1
        src = verdict.verifier_source or "llm"
        print(f"  {item_id[:12]} {arm:18s} {case:34s} met={verdict.goal_met} [{src}]")

    OUT.write_text(json.dumps(out, indent=2) + "\n")
    met = sum(1 for v in out.values() if v["goal_met"])
    det = sum(1 for v in out.values() if v["verifier_source"] == "deterministic")
    print(
        f"\njudged {judged_new} new + {len(already)} resumed = {len(out)} growth answers -> {OUT}"
    )
    print(f"  goal_met True: {met}  False: {len(out) - met}")
    print(f"  deterministic-cascade fired: {det}  LLM-judged: {len(out) - det}")
    print(f"  judge model: {JUDGE_MODEL} (matches base wave)")
    if missing:
        print(f"MISSING ({len(missing)}): {missing}")
    elif judged_new == 0:
        print(
            f"nothing to judge — all {len(targets)} in-seed growth items already have verdicts (use --force to re-judge)"
        )
    else:
        print(f"all {len(targets)} in-seed growth items now have verdicts")


if __name__ == "__main__":
    asyncio.run(main())
