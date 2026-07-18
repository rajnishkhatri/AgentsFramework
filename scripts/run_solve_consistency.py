"""Step-4 solve-consistency gate for a promoted (still reviewed=false) bank.

Answer-blind solvers from *different* MODEL_PROFILE_SET families must recover
the declared key unanimously. Disagreement / undecidable → quarantine list
(AP-6). This job NEVER flips ``reviewed`` — Step 5 owns that flag.

Uses a direct one-shot LLM call (no tool-bound ReAct graph) so letter replies
are not swallowed by tool-call turns. Live-LLM, on-demand — NEVER in CI.

Usage:

    .venv/bin/python scripts/run_solve_consistency.py \\
        --items research/.../coach-item-bank-gen2.promoted.json \\
        --out docs/questionbank/coach-bank-gen2-step4-solve.json \\
        --families openai,anthropic \\
        [--limit 20] [--min-difficulty 4] [--resume]
"""

# ruff: noqa: E402 — dotenv bootstrap must precede repo imports.

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parent.parent
load_dotenv(_REPO / ".env")

from services.observability import setup_logging

setup_logging(_REPO / "logging.json")

from components.test_item_generation import _solver_view, extract_solver_letter
from services import eval_capture
from services.base_config import AgentConfig, ModelProfile
from services.llm_config import LLMService, build_model_registry, response_text
from services.prompt_service import PromptService

SUBJECT = "act-english"
SOLVE_TARGET = "test_item_solve_consistency"

__all__ = ["adjudicate_votes"]


def adjudicate_votes(*, key: str, votes: dict[str, str | None]) -> str:
    """Classify a multi-family vote set against the declared key.

    Returns one of: ``pass``, ``mismatch``, ``disagree``, ``undecidable``.
    """
    if not votes:
        return "undecidable"
    letters = list(votes.values())
    if any(v is None for v in letters):
        return "undecidable"
    distinct = set(letters)
    if len(distinct) != 1:
        return "disagree"
    only = next(iter(distinct))
    if only != key:
        return "mismatch"
    return "pass"


def _profile_for_tier(profile_set: str, tier: str) -> ModelProfile:
    models, _ = build_model_registry(profile_set)
    for profile in models:
        if profile.tier == tier:
            return profile.model_copy(deep=True)
    raise SystemExit(f"no {tier!r} profile in MODEL_PROFILE_SET={profile_set!r}")


def _make_family_solver(
    profile_set: str,
    *,
    capable_difficulty: int | None,
    prompts: PromptService,
):
    """One family: direct one-shot solve; capable tier for difficulty >= threshold."""
    fast = _profile_for_tier(profile_set, "fast")
    capable = (
        _profile_for_tier(profile_set, "capable")
        if capable_difficulty is not None
        else None
    )
    models = [fast] + ([capable] if capable is not None else [])
    cfg = AgentConfig(default_model=fast.name, models=models)
    llm = LLMService(cfg)
    label = (
        f"{fast.name}+{capable.name}>=d{capable_difficulty}"
        if capable is not None and capable_difficulty is not None
        else fast.name
    )

    async def solve(item: dict[str, Any]) -> str:
        difficulty = item.get("difficulty")
        profile = fast
        if (
            capable is not None
            and capable_difficulty is not None
            and isinstance(difficulty, int)
            and difficulty >= capable_difficulty
        ):
            profile = capable
        view = _solver_view(item)
        task_input = prompts.render_prompt(
            "test_item_solver", subject=SUBJECT, item=view
        )
        run_id = uuid.uuid4().hex
        response = await llm.invoke(profile, [{"role": "user", "content": task_input}])
        text = response_text(response)
        await eval_capture.record(
            target=SOLVE_TARGET,
            ai_input={"item_id": item.get("id"), "family": profile_set},
            ai_response={"text": text[:200], "model": profile.name},
            config={
                "configurable": {
                    "task_id": f"s4solve-{run_id}",
                    "user_id": "solve-consistency",
                }
            },
        )
        return text

    return f"{profile_set}:{label}", solve


async def _solve_item(
    item: dict[str, Any],
    solvers: list[tuple[str, Any]],
) -> dict[str, Any]:
    letters = {c["letter"] for c in item["choices"]}
    labels = [label for label, _ in solvers]
    replies = await asyncio.gather(*[solve(item) for _, solve in solvers])
    raw = {label: reply for label, reply in zip(labels, replies, strict=True)}
    votes = {
        label: extract_solver_letter(reply, letters) for label, reply in raw.items()
    }
    status = adjudicate_votes(key=item["answer_letter"], votes=votes)
    return {
        "id": item["id"],
        "difficulty": item.get("difficulty"),
        "skill_id": item.get("skill_id"),
        "answer_letter": item["answer_letter"],
        "votes": votes,
        "raw_replies": {k: (v[:80] if v else "") for k, v in raw.items()},
        "status": status,
        "reviewed": item.get("reviewed"),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--families",
        default="openai,anthropic",
        help="Comma-separated MODEL_PROFILE_SET names (different families).",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--min-difficulty",
        type=int,
        default=None,
        help="If set, only items with difficulty >= this value are solved.",
    )
    parser.add_argument(
        "--capable-difficulty",
        type=int,
        default=4,
        help="Within each family, route d>=N to capable (default 4; 0=off).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip ids already present in --out.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max items in flight (families still fan out per item).",
    )
    args = parser.parse_args()

    families = [f.strip() for f in args.families.split(",") if f.strip()]
    if len(families) < 2:
        raise SystemExit("Step 4 requires >=2 families (different model families)")

    items: list[dict[str, Any]] = json.loads(args.items.read_text())
    if args.min_difficulty is not None:
        items = [
            r
            for r in items
            if isinstance(r.get("difficulty"), int)
            and r["difficulty"] >= args.min_difficulty
        ]
    items = items[args.offset :]
    if args.limit is not None:
        items = items[: args.limit]

    done: dict[str, dict[str, Any]] = {}
    if args.resume and args.out.exists():
        prev = json.loads(args.out.read_text())
        for row in prev.get("rows", []):
            done[row["id"]] = row
        items = [r for r in items if r["id"] not in done]

    capable_d = None if args.capable_difficulty == 0 else args.capable_difficulty
    prompts = PromptService()
    solvers: list[tuple[str, Any]] = []
    family_labels: list[str] = []
    for fam in families:
        label, solve = _make_family_solver(
            fam, capable_difficulty=capable_d, prompts=prompts
        )
        solvers.append((label, solve))
        family_labels.append(label)

    run_id = uuid.uuid4().hex
    rows = list(done.values())
    counts = {"pass": 0, "mismatch": 0, "disagree": 0, "undecidable": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print(
        f"solve-consistency run={run_id} families={family_labels} "
        f"pending={len(items)} resumed={len(done)}"
    )

    if not items and not rows:
        args.out.write_text(
            json.dumps(
                {
                    "gate": "step4-solve-consistency",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "run_id": run_id,
                    "families": family_labels,
                    "verdict": "EMPTY",
                    "counts": counts,
                    "quarantine_ids": [],
                    "rows": [],
                    "note": "reviewed flags are never flipped by this job",
                },
                indent=2,
            )
            + "\n"
        )
        print("DONE verdict=EMPTY (no items)")
        return

    sem = asyncio.Semaphore(max(1, args.concurrency))
    lock = asyncio.Lock()
    done_n = 0

    async def _one(item: dict[str, Any]) -> None:
        nonlocal done_n
        if item.get("reviewed") is True:
            print(f"SKIP {item['id']}: already reviewed=true (not this job's lot)")
            return
        async with sem:
            result = await _solve_item(item, solvers)
        async with lock:
            rows.append(result)
            counts[result["status"]] = counts.get(result["status"], 0) + 1
            done_n += 1
            pending_left = len(items) - done_n
            if counts["pass"] == len(rows) and pending_left == 0:
                verdict = "PASS"
            elif pending_left == 0:
                verdict = "FAIL"
            else:
                verdict = "PENDING"
            print(
                f"[{done_n}/{len(items)}] {result['id']} d={result['difficulty']} "
                f"→ {result['status']} votes={result['votes']}"
            )
            report = {
                "gate": "step4-solve-consistency",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "families": family_labels,
                "source_items": str(args.items),
                "n_scored": len(rows),
                "counts": dict(counts),
                "quarantine_ids": [r["id"] for r in rows if r["status"] != "pass"],
                "verdict": verdict,
                "note": "reviewed flags are never flipped by this job",
                "rows": rows,
            }
            args.out.write_text(json.dumps(report, indent=2) + "\n")

    await asyncio.gather(*[_one(item) for item in items])

    final = json.loads(args.out.read_text())
    print(
        f"DONE verdict={final.get('verdict')} counts={final.get('counts')} "
        f"quarantine={len(final.get('quarantine_ids', []))} -> {args.out}"
    )


if __name__ == "__main__":
    asyncio.run(main())
