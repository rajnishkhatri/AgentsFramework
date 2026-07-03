"""Offline hint-ladder generator — a governed ``build_graph`` job (Phase 4).

Drives the SAME capability-gated coach contract as the live agent
(``subject_coach_agent_config`` + ``bound_capabilities``), so generation runs
carry the full governance carriers (identity, capability gate, guardrails —
ADR-0007). Per question: render ``prompts/hint_generator.j2`` → one graph run
→ ``components.hint_generation.run_hint_cascade`` adjudicates. PASS rows
(``reviewed=True``, earned) land in the output JSON; quarantined rows are
recorded via ``eval_capture`` with ``target="hint_generator"`` for the §12
error-analysis loop. Provenance: ``generated_by = "<model>@<workflow_id>"``.

Live-LLM, on-demand — NEVER in CI. Usage:

    .venv/bin/python scripts/generate_hints.py --questions questions.json \
        --out generated_hints.json [--existing existing_hints.json]

``questions.json``: a list of question objects (id, stem_md, choices,
answer_letter, why_correct_md, ...). ``--existing``: prior hint rows whose
bodies feed the duplicate stage.
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

# Route eval_capture to logs/evals.log (the quarantine records are the §12
# error-analysis feed) — a bare script has no logging config otherwise.
import logging.config

logging.config.dictConfig(json.loads((_REPO / "logging.json").read_text()))

from components.hint_generation import run_hint_cascade
from services import eval_capture
from services.base_config import default_fast_profile
from services.governance.subject_coach_identity import (
    SUBJECT_COACH_CAPABILITIES,
    subject_coach_agent_config,
)
from services.prompt_service import PromptService

SUBJECT = "act-english"


async def generate_for_question(
    graph,
    prompts: PromptService,
    question: dict,
    existing_bodies: list[str],
    model: str,
) -> tuple[list[dict], list[dict]]:
    task_input = prompts.render_prompt(
        "hint_generator", subject=SUBJECT, question=question
    )
    workflow_id = uuid.uuid4().hex
    result = await graph.ainvoke(
        {
            "task_id": f"hintgen-{question['id']}",
            "task_input": task_input,
            "messages": [],
            "workflow_id": workflow_id,
        },
        config={
            "configurable": {
                "task_id": f"hintgen-{question['id']}",
                "user_id": "hint-generator",
            }
        },
    )
    reply = str(result.get("last_final_answer") or "")
    verdict = run_hint_cascade(
        reply,
        question=question,
        subject=SUBJECT,
        existing_bodies=existing_bodies,
        generated_by=f"{model}@{workflow_id}",
    )
    for row in verdict.quarantined:
        await eval_capture.record(
            target="hint_generator",
            ai_input={"question_id": question["id"], "stage": row["stage"]},
            ai_response={"violations": row["violations"], "raw": str(row["raw"])[:500]},
            config={
                "configurable": {
                    "task_id": f"hintgen-{question['id']}",
                    "user_id": "hint-generator",
                }
            },
        )
    return verdict.passed, verdict.quarantined


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--existing", type=Path, default=None)
    args = parser.parse_args()

    questions = json.loads(args.questions.read_text())
    existing_bodies: list[str] = []
    if args.existing and args.existing.exists():
        existing_bodies = [r["body_md"] for r in json.loads(args.existing.read_text())]

    profile = default_fast_profile()
    # Two deliberate overrides on the coach contract:
    # - eval_capture_target: generation turns must NEVER masquerade as coach
    #   shadow traffic (target="subject_coach" feeds the Phase-3 coding corpus
    #   and the judge sampler) — they get their own stream.
    # - input_guardrail_accept_condition="": the domain condition guards
    #   UNTRUSTED learner utterances; the generator's input is our own
    #   rendered template (first-party), and the live smoke showed the judge
    #   rejecting a hint-generation meta-prompt as "off-topic". The
    #   prompt-injection rail still runs; identity + capability gate stay.
    cfg = subject_coach_agent_config(
        default_model=profile.name,
        models=[profile],
        eval_capture_target="hint_generator_llm",
        input_guardrail_accept_condition="",
    )

    from orchestration.react_loop import build_graph
    from services.tools.file_io import FileIOInput, execute_file_io
    from services.tools.registry import ToolDefinition, ToolRegistry
    from services.tools.think_tool import ThinkToolInput, execute_think_tool

    # The coach's least-privilege registry: exactly the declared capabilities
    # (think + file_io), so the ADR-0007 gate binds declared == bound on every
    # generation run too.
    tool_registry = ToolRegistry(
        {
            "think": ToolDefinition(executor=execute_think_tool, schema=ThinkToolInput),
            "file_io": ToolDefinition(
                executor=execute_file_io, schema=FileIOInput, cacheable=False
            ),
        }
    )
    graph = build_graph(
        agent_config=cfg,
        tool_registry=tool_registry,
        bound_capabilities=list(SUBJECT_COACH_CAPABILITIES),
    )
    prompts = PromptService()

    all_rows: list[dict] = []
    total_quarantined = 0
    for question in questions:
        rows, quarantined = await generate_for_question(
            graph, prompts, question, existing_bodies, profile.name
        )
        all_rows.extend(rows)
        existing_bodies.extend(r["body_md"] for r in rows)
        total_quarantined += len(quarantined)
        print(
            f"{question['id']}: {len(rows)} reviewed rung(s), "
            f"{len(quarantined)} quarantined"
        )

    args.out.write_text(json.dumps(all_rows, indent=1))
    print(
        f"\nDONE: {len(all_rows)} reviewed rows -> {args.out} "
        f"({total_quarantined} quarantined -> eval_capture target=hint_generator)"
    )


if __name__ == "__main__":
    asyncio.run(main())
