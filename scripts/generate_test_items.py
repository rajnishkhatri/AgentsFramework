"""Offline test-item generator — a governed ``build_graph`` job (Phase 6).

Drives the SAME capability-gated coach contract as the live agent, so
generation runs carry the full governance carriers (identity, capability gate —
ADR-0007). The cascade's critical gate is an INDEPENDENT solver pass: a second
graph invocation sees the stem + choices ONLY (the declared key withheld) and
its letter must match, or the item is quarantined (ADR-0015 clause 5).

Two modes:
  * generate (default): render ``prompts/test_item_generator.j2`` → one graph
    run → ``run_test_item_cascade`` adjudicates each candidate.
  * ``--import-seed``: read a neutral ``reviewed=false`` seed and run the SAME
    cascade to promote rows (task 6.5). Promotion re-stamps ``generated_by``.

PASS rows (``reviewed=True``, earned) land in the output JSON; quarantined rows
are recorded via ``eval_capture`` with ``target="test_item_generator"``.

Live-LLM, on-demand — NEVER in CI. Usage:

    .venv/bin/python scripts/generate_test_items.py --count 5 \
        --out generated_items.json [--existing existing_items.json]
"""

# ruff: noqa: E402 — dotenv bootstrap must precede repo imports.

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parent.parent
load_dotenv(_REPO / ".env")

import logging.config

logging.config.dictConfig(json.loads((_REPO / "logging.json").read_text()))

from langgraph.errors import GraphRecursionError

from components.test_item_generation import run_test_item_cascade
from services import eval_capture
from services.base_config import default_fast_profile
from services.governance.subject_coach_identity import (
    SUBJECT_COACH_CAPABILITIES,
    subject_coach_agent_config,
)
from services.prompt_service import PromptService

SUBJECT = "act-english"
TEST_ITEM_TARGET = "test_item_generator_llm"


def build_generator_config():
    """The governed generator's AgentConfig — the coach contract with the two
    deliberate overrides (the ``generate_hints.py`` precedent):

    - ``eval_capture_target``: generation turns get their OWN stream, never
      masquerading as coach shadow traffic (``subject_coach``) or the hint
      stream — the eval streams stay isolated.
    - ``input_guardrail_accept_condition=""``: the learner-domain condition
      guards UNTRUSTED utterances; the generator's input is our own rendered
      template (first-party). The prompt-injection rail still runs; identity +
      capability gate stay.
    """
    profile = default_fast_profile()
    return subject_coach_agent_config(
        default_model=profile.name,
        models=[profile],
        eval_capture_target=TEST_ITEM_TARGET,
        input_guardrail_accept_condition="",
    )


def _build_graph(cfg):
    from orchestration.react_loop import build_graph
    from services.tools.file_io import FileIOInput, execute_file_io
    from services.tools.registry import ToolDefinition, ToolRegistry
    from services.tools.think_tool import ThinkToolInput, execute_think_tool

    tool_registry = ToolRegistry(
        {
            "think": ToolDefinition(executor=execute_think_tool, schema=ThinkToolInput),
            "file_io": ToolDefinition(
                executor=execute_file_io, schema=FileIOInput, cacheable=False
            ),
        }
    )
    return build_graph(
        agent_config=cfg,
        tool_registry=tool_registry,
        bound_capabilities=list(SUBJECT_COACH_CAPABILITIES),
    )


def _make_solver(graph, prompts: PromptService):
    """An injected solver closure over the governed graph: renders the solver
    prompt (key already withheld by ``_solver_view``) and returns the reply.
    One LLM call per candidate item (FR-23.3)."""

    async def solve(item) -> str:
        # The solver is a ONE-SHOT classification, not a ReAct task: it names a
        # letter and stops. The general success-conditions evaluator does not
        # recognize a bare "B" as task-complete, so the graph would re-plan the
        # same call until GraphRecursionError. We only need step 0's answer
        # (`last_final_answer` is set on every evaluate), so bound recursion and
        # read the first answer — treating a recursion trip as "answer captured".
        task_input = prompts.render_prompt(
            "test_item_solver", subject=SUBJECT, item=item
        )
        run_id = uuid.uuid4().hex
        payload = {
            "task_id": f"tisolve-{run_id}",
            "task_input": task_input,
            "messages": [],
            "workflow_id": run_id,
        }
        config = {
            "recursion_limit": 6,
            "configurable": {
                "task_id": f"tisolve-{run_id}",
                "user_id": "test-item-solver",
            },
        }
        # Stream state updates and grab the FIRST assistant message (the solver's
        # letter), then stop — no checkpointer needed, and the ReAct re-plan loop
        # never runs to exhaustion. The solver replies with a terse letter that
        # the generic success-conditions evaluator never accepts as "done", so a
        # full ainvoke would GraphRecursionError; we only need that first answer
        # (it surfaces in `messages` a few supersteps in). A trip before any
        # assistant message yields "".
        answer = ""
        try:
            async for update in graph.astream(
                payload, config=config, stream_mode="values"
            ):
                ai_messages = [
                    m
                    for m in update.get("messages", [])
                    if type(m).__name__ == "AIMessage"
                ]
                if ai_messages:
                    answer = str(getattr(ai_messages[-1], "content", "") or "")
                    break
        except GraphRecursionError:
            pass
        return answer

    return solve


async def _run_generation(graph, prompts, count, existing_stems, generated_by):
    task_input = prompts.render_prompt(
        "test_item_generator", subject=SUBJECT, count=count, skill_id=None
    )
    workflow_id = uuid.uuid4().hex
    result = await graph.ainvoke(
        {
            "task_id": f"tigen-{workflow_id}",
            "task_input": task_input,
            "messages": [],
            "workflow_id": workflow_id,
        },
        config={
            "configurable": {
                "task_id": f"tigen-{workflow_id}",
                "user_id": "test-item-generator",
            }
        },
    )
    reply = str(result.get("last_final_answer") or "")
    verdict = await run_test_item_cascade(
        reply,
        subject=SUBJECT,
        solver=_make_solver(graph, prompts),
        existing_stems=existing_stems,
        generated_by=generated_by,
    )
    await _record_quarantines(verdict.quarantined, task_id=f"tigen-{workflow_id}")
    return verdict


async def _record_quarantines(quarantined, *, task_id):
    for row in quarantined:
        await eval_capture.record(
            target="test_item_generator",
            ai_input={"stage": row["stage"]},
            ai_response={"violations": row["violations"], "raw": str(row["raw"])[:500]},
            config={
                "configurable": {"task_id": task_id, "user_id": "test-item-generator"}
            },
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--existing", type=Path, default=None)
    parser.add_argument(
        "--import-seed",
        type=Path,
        default=None,
        help="Promote a reviewed=false seed through the cascade (task 6.5).",
    )
    args = parser.parse_args()

    existing_stems: list[str] = []
    if args.existing and args.existing.exists():
        existing_stems = [r["stem_md"] for r in json.loads(args.existing.read_text())]

    profile = default_fast_profile()
    cfg = build_generator_config()
    graph = _build_graph(cfg)
    prompts = PromptService()
    generated_by = f"{profile.name}@{uuid.uuid4().hex}"

    if args.import_seed is not None:
        from scripts.promote_test_item_seed import promote_seed

        verdict = await promote_seed(
            args.import_seed,
            solver=_make_solver(graph, prompts),
            existing_stems=existing_stems,
            generated_by=generated_by,
        )
    else:
        verdict = await _run_generation(
            graph, prompts, args.count, existing_stems, generated_by
        )

    args.out.write_text(json.dumps(verdict.passed, indent=1))
    print(
        f"DONE: {len(verdict.passed)} reviewed item(s) -> {args.out} "
        f"({len(verdict.quarantined)} quarantined -> "
        f"eval_capture target=test_item_generator)"
    )


if __name__ == "__main__":
    asyncio.run(main())
