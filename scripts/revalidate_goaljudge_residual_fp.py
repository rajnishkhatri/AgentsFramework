"""Live re-judge of the 2 residual GoalJudge false-downgrades (prompt-fix proof).

The semantic-satisfaction clause in ``prompts/goal_judge_system_prompt.j2`` is a
prompt change — its effect on ``goal_met`` cannot be measured offline (the CI tests
pin only that the clause renders + the guards survive). This script does the
authorised LIVE re-judge: it drives the REAL :class:`~components.goal_judge.GoalJudge`
(same judge model the corpus used — ``gpt-4o``) over the two cases' stored
**full** answers (the 8192-char view the live judge saw, NOT the 500-char harvest)
and reports the new verdict.

Expected:
  - ``70ff3369`` GEN-L3-iterative-refine-15 (budget-offset): the answer verifies the
    offset as "fully offset, no category cut below its actual spend" — the clause
    should now let that satisfy "verify the offset balances to zero" → goal_met=True.
  - ``df252d51`` GEN-L3-multi-hop-synthesis-14 (citation): the answer states paper-3's
    TITLE, never its CLAIM — the clause keys on outcome-present, so this MUST stay
    goal_met=False (the judge was right; the gold label was lenient).

Each case is judged N times (LLM nondeterminism) and the verdict distribution is
reported. No corpus is mutated; this writes only a small JSON proof artifact.

Run:  .venv/bin/python -m scripts.revalidate_goaljudge_residual_fp [--n 5]
Requires OPENAI_API_KEY (loaded from .env).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv

load_dotenv(AGENT_ROOT / ".env")

from components.goal_judge import GoalJudge  # noqa: E402
from services.base_config import AgentConfig  # noqa: E402
from services.llm_config import LLMService, build_model_registry  # noqa: E402
from services.prompt_service import PromptService  # noqa: E402

OUT = AGENT_ROOT / "cache" / "goaljudge_eval" / "residual_fp_revalidation.json"

# Judge model the corpus used (from the evals.log goal_judge records). The
# prompt-fix proof is DIRECTIONAL (does the clause flip 70ff3369 to met while
# df252d51 stays not-met), so any capable judge model validates it; gpt-4o is
# preferred for apples-to-apples but is selectable via --judge-model if its
# quota is exhausted. The chosen model is recorded in the proof artifact.
DEFAULT_JUDGE_MODEL = "gpt-4o"

# ── the two cases: task + stored FULL answer (8192-char judge view) + evidence ──
# Evidence is the canonical seeded bytes (scripts/seed_model_ab_l2l3_workspace.py),
# identical to what the agent read at runtime.

BUDGET_TASK = (
    "Read /workspace/budget.csv (category,planned,actual). Identify every category "
    "over budget, compute the total overrun, then propose a set of cuts to "
    "under-budget categories that fully offsets the overrun WITHOUT cutting any "
    "category below its actual spend. Report the proposed cuts and verify the "
    "offset balances to zero."
)
BUDGET_ANSWER = (
    "FINAL ANSWER:\n\n**Budget Analysis and Cut Proposal**\n\n**Data:**\n\n"
    "| Category | Planned | Actual | Status |\n"
    "|----------|---------|--------|--------|\n"
    "| food     | 100     | 130    | Over by 30 |\n"
    "| travel   | 200     | 150    | Under by 50 |\n"
    "| office   | 80      | 60     | Under by 20 |\n"
    "| rent     | 500     | 500    | On budget |\n\n"
    "**Overrun:** Only `food` is over budget, by **30**.\n\n"
    "**Slack (room for cuts without going below actual spend):**\n"
    "- `travel`: up to 50 (from 200 down to 150)\n"
    "- `office`: up to 20 (from 80 down to 60)\n"
    "- Total slack available: 70\n\n"
    "**Proposed Cut:** Reduce the **travel** category's planned budget from "
    "**200 to 170** (a cut of **30**). This fully offsets the 30 overrun from food, "
    "and travel's new planned amount (170) remains safely above its actual spend "
    "(150).\n\n"
    "The total planned budget changes from 880 to 850, matching the total actual "
    "spend of 840 plus 10 in remaining slack (office still has 20 un-cut). "
    "The overrun is fully offset with no category cut below its actual spend."
)
BUDGET_EVIDENCE = [
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/budget.csv", "operation": "read"},
        "tool_output": (
            "category,planned,actual\n"
            "food,100,130\ntravel,200,150\noffice,80,60\nrent,500,500\n"
        ),
    }
]

CITATION_TASK = (
    "Read /workspace/papers/ (paper-1.txt … paper-4.txt). Each paper cites others "
    "by their number in a 'cites:' line. Build the citation graph, find the paper "
    "cited by the most others, then summarise THAT paper's key claim and explain "
    "which papers depend on it and why. Read every paper before answering."
)
CITATION_ANSWER = (
    "Perfect! I've successfully analyzed the citation graph and created a "
    "comprehensive report. Here's the summary:\n\n## FINAL ANSWER:\n\n"
    "**Citation Graph Analysis Complete**\n\n### Papers Overview:\n"
    "- **Paper 1**: Caching strategies (cites Paper 3)\n"
    "- **Paper 2**: Index tuning (cites Paper 3)\n"
    "- **Paper 3**: Foundations of locality (no citations - foundational)\n"
    "- **Paper 4**: Prefetching (cites Paper 3)\n\n"
    "### Dependency Structure:\n"
    "The citation graph forms a **star topology** with Paper 3 at the center:\n"
    "- Paper 3 is foundational with no dependencies\n"
    "- Papers 1, 2, and 4 all depend on Paper 3\n"
    "- Papers 1, 2, and 4 are independent of each other\n\n"
    "### Recommended Reading Order:\n"
    "1. **Phase 1**: Read Paper 3 first (Foundations of locality)\n"
    "2. **Phase 2**: Read Papers 1, 2, and 4 in any order (they can be read in "
    "parallel)\n\n### Key Insight:\n"
    "Paper 3 provides the foundational concepts about locality that are applied in "
    "three different contexts: caching strategies, index tuning, and prefetching. "
    "There are no circular dependencies, making this a clean, acyclic dependency graph."
)
CITATION_EVIDENCE = [
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-1.txt"},
        "tool_output": "Title: Caching strategies.\nClaim: LRU beats FIFO under skew.\ncites: 3\n",
    },
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-2.txt"},
        "tool_output": "Title: Index tuning.\nClaim: Covering indexes cut IO.\ncites: 3\n",
    },
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-3.txt"},
        "tool_output": "Title: Foundations of locality.\nClaim: Temporal locality dominates real workloads.\ncites: \n",
    },
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-4.txt"},
        "tool_output": "Title: Prefetching.\nClaim: Prefetch depth 2 is optimal.\ncites: 3\n",
    },
]

CASES = [
    {
        "item": "70ff3369",
        "case": "GEN-L3-iterative-refine-15",
        "task": BUDGET_TASK,
        "answer": BUDGET_ANSWER,
        "evidence": BUDGET_EVIDENCE,
        "expect_met": True,
        "note": "echo false-downgrade — verification present, phrased 'fully offset'",
    },
    {
        "item": "df252d51",
        "case": "GEN-L3-multi-hop-synthesis-14",
        "task": CITATION_TASK,
        "answer": CITATION_ANSWER,
        "evidence": CITATION_EVIDENCE,
        "expect_met": False,
        "note": "judge was right — answer states paper-3 TITLE, never its CLAIM",
    },
]


def _build_judge(judge_model: str) -> tuple[GoalJudge, str]:
    models, default_model = build_model_registry("all")
    config = AgentConfig(default_model=default_model, models=models)
    llm = LLMService(config)
    return GoalJudge(
        llm_service=llm,
        prompt_service=PromptService(),
        judge_profile=llm.get_profile(judge_model),
    ), judge_model


async def _judge_n(judge: GoalJudge, case: dict, n: int) -> list[dict]:
    verdicts = []
    for _ in range(n):
        v = await judge.evaluate(
            task_input=case["task"],
            final_answer=case["answer"],
            success_conditions=[],
            evidence=case["evidence"],
        )
        verdicts.append(
            {
                "goal_met": v.goal_met,
                "criteria_met": v.criteria_met,
                "partial_fraction": v.partial_fraction,
                "verifier_source": v.verifier_source,
                "rationale": v.rationale,
            }
        )
    return verdicts


async def main(n: int, judge_model: str) -> None:
    judge, judge_model = _build_judge(judge_model)
    results = []
    all_ok = True
    for case in CASES:
        verdicts = await _judge_n(judge, case, n)
        met_count = sum(1 for v in verdicts if v["goal_met"])
        # Pass = the EXPECTED verdict is the majority (LLM nondeterminism tolerant).
        majority_met = met_count > n / 2
        ok = majority_met == case["expect_met"]
        all_ok = all_ok and ok
        results.append(
            {
                **{k: case[k] for k in ("item", "case", "expect_met", "note")},
                "n": n,
                "met_count": met_count,
                "majority_met": majority_met,
                "matches_expectation": ok,
                "verdicts": verdicts,
            }
        )
        flag = "OK " if ok else "XX "
        print(f"{flag}{case['item']} {case['case']}")
        print(
            f"    expect goal_met={case['expect_met']} | "
            f"got met {met_count}/{n} → majority={majority_met}"
        )
        for v in verdicts:
            print(
                f"      goal_met={v['goal_met']} "
                f"pf={v['partial_fraction']} src={v['verifier_source']} :: "
                f"{v['rationale'][:150]}"
            )
        print()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"judge_model": judge_model, "n": n, "all_match": all_ok, "cases": results},
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {OUT}")
    print(f"judge_model={judge_model}  ALL MATCH EXPECTATION: {all_ok}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5, help="re-judge repeats per case")
    ap.add_argument(
        "--judge-model",
        default=DEFAULT_JUDGE_MODEL,
        help="judge ModelProfile name (e.g. gpt-4o, claude-haiku-4-5)",
    )
    args = ap.parse_args()
    asyncio.run(main(args.n, args.judge_model))
