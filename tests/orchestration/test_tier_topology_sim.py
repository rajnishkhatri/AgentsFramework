"""Protocol-D topology simulation for the Phase 1 (T1) replan gate.

Executes the compiled graph (L4 simulation) with scripted LLM responses and a
tool that can be made to fail, so the brittle-plan risk (plan §9) is the named
failure row: a *surprising* (failed) tool result must trigger a replan, while a
clean run must not. No live model — deterministic, CI-safe (AP5).

The replan gate lives in ``route_node`` (it reuses the memoized plan and rebuilds
only when ``plan_is_stale`` fires on the latest tool result), so the loop
``route -> call_llm -> execute_tool -> evaluate -> route`` carries the signal
through the existing continue edge — no new graph edge. This test asserts the
observable effect end-to-end: ``replan_count`` and the ``replanned`` STEP_PLANNED
flag.

CI policy (TDD Self-Validation Check 8): this is a Protocol-D / Layer-4
simulation but is **intentionally CI-resident** (no ``@pytest.mark.simulation``).
The marker exists to fence L4 tests that are slow/expensive/flaky because they
hit live models — none of which applies here: the LLM is fully mocked
(``ChatLiteLLM.ainvoke`` patched, AP5-safe), the run is ~3s, and it is
deterministic with zero flake. It guards the replan-gate wiring, exactly the
regression worth catching per-commit, so it deliberately stays in the default
gate rather than being deferred to on-demand.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from services.base_config import AgentConfig, ModelProfile
from services.tools.registry import (
    ToolDefinition,
    ToolExecutionResult,
    ToolRegistry,
)


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _capable_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015,
    )


class _ProbeInput(BaseModel):
    note: str = ""


def _make_probe_tool(fail_first: bool):
    """A probe tool whose FIRST call optionally fails, then succeeds."""
    state = {"calls": 0}

    def _executor(args: dict) -> ToolExecutionResult:
        state["calls"] += 1
        if fail_first and state["calls"] == 1:
            return ToolExecutionResult(
                output="Error: probe failed", ok=False, error="probe failed"
            )
        return ToolExecutionResult(output="probe ok", ok=True)

    return _executor


def _registry(fail_first: bool) -> ToolRegistry:
    return ToolRegistry({
        "probe": ToolDefinition(
            executor=_make_probe_tool(fail_first),
            schema=_ProbeInput,
            cacheable=False,
        ),
    })


def _resp(content: str, tool_calls: list[dict], idx: int) -> MagicMock:
    response = MagicMock()
    response.content = content
    response.tool_calls = [
        {
            "name": tc["name"],
            "args": tc["args"],
            "id": f"tc-{idx}-{pos}",
            "type": "tool_call",
        }
        for pos, tc in enumerate(tool_calls)
    ]
    response.usage_metadata = {
        "input_tokens": 50,
        "output_tokens": 20,
        "total_tokens": 70,
    }
    response.response_metadata = {"model_name": "gpt-4o-mini"}
    return response


# An L1 task (leading strong-intent verb "Plan" -> strong-intent-verb floor).
_TASK = "Plan the database migration and apply it carefully."


async def _run(fail_first: bool, tmp_path):
    from orchestration.react_loop import build_graph

    # Script: call probe, call probe again, then a final answer.
    script = [
        _resp("", [{"name": "probe", "args": {"note": "first"}}], 0),
        _resp("", [{"name": "probe", "args": {"note": "second"}}], 1),
        _resp("Migration planned and applied.", [], 2),
    ]

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChat,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
    ):
        inst = MockChat.return_value
        inst.bind_tools.return_value = inst
        inst.ainvoke = AsyncMock(side_effect=script)

        graph = build_graph(
            agent_config=AgentConfig(
                default_model="gpt-4o-mini",
                models=[_fast_profile(), _capable_profile()],
            ),
            tool_registry=_registry(fail_first),
            cache_dir=tmp_path / "cache",
        )

        wf = f"wf-replan-{fail_first}"
        return await graph.ainvoke(
            {
                "task_id": f"task-replan-{fail_first}",
                "task_input": _TASK,
                "messages": [],
                "workflow_id": wf,
                "registered_agent_id": "sim-agent",
            },
            config={
                "configurable": {
                    "task_id": f"task-replan-{fail_first}",
                    "user_id": "sim-user",
                    "workflow_id": wf,
                    "registered_agent_id": "sim-agent",
                }
            },
        )


@pytest.mark.asyncio
async def test_surprising_tool_result_triggers_replan(tmp_path):
    """Protocol-D / brittle-plan row: a failed tool result re-plans."""
    result = await _run(fail_first=True, tmp_path=tmp_path)
    # The plan was rebuilt at least once after the surprising result.
    assert result.get("replan_count", 0) >= 1
    # The depth held (memoized L1) — replan does not collapse the plan.
    assert result.get("planning_depth") == "L1"


@pytest.mark.asyncio
async def test_stable_run_does_not_replan(tmp_path):
    """Control: an all-success run never triggers a replan."""
    result = await _run(fail_first=False, tmp_path=tmp_path)
    assert result.get("replan_count", 0) == 0
    assert result.get("planning_depth") == "L1"


@pytest.mark.asyncio
async def test_generated_plan_source_consumes_llm_plan(tmp_path):
    """plan_source='generated': the LLM plan is consumed (with the floor backstop).

    The plan generator shares the mocked ``ainvoke``; at step 0 route_node calls
    it BEFORE the first call_llm, so the plan JSON is the first scripted response.
    """
    from orchestration.react_loop import build_graph

    plan_json = json.dumps({
        "ordered_steps": [
            {"title": "Inventory", "goal": "inventory the schema objects"},
            {"title": "Backfill", "goal": "write the backfill migration"},
            {"title": "Cutover", "goal": "cut over with a rollback plan"},
        ],
        "constraints": ["no downtime"],
        "success_conditions": ["the migration is applied and reversible"],
    })
    script = [
        _resp(plan_json, [], 0),  # plan generator's call (step 0, in route_node)
        _resp("", [{"name": "probe", "args": {"note": "go"}}], 1),
        _resp("Done.", [], 2),
    ]

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChat,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
    ):
        inst = MockChat.return_value
        inst.bind_tools.return_value = inst
        inst.ainvoke = AsyncMock(side_effect=script)

        graph = build_graph(
            agent_config=AgentConfig(
                default_model="gpt-4o-mini",
                models=[_fast_profile(), _capable_profile()],
                plan_source="generated",
            ),
            tool_registry=_registry(fail_first=False),
            cache_dir=tmp_path / "cache",
        )

        wf = "wf-gen-plan"
        result = await graph.ainvoke(
            {
                "task_id": "task-gen-plan",
                "task_input": _TASK,
                "messages": [],
                "workflow_id": wf,
                "registered_agent_id": "sim-agent",
            },
            config={
                "configurable": {
                    "task_id": "task-gen-plan",
                    "user_id": "sim-user",
                    "workflow_id": wf,
                    "registered_agent_id": "sim-agent",
                }
            },
        )

    # The consumed plan is the LLM one (3 steps from the generator), not the
    # deterministic floor for this task (which yields a single step).
    artifact = result.get("plan_artifact") or {}
    goals = [s["goal"] for s in artifact.get("ordered_steps", [])]
    assert "inventory the schema objects" in goals
    assert len(goals) == 3


# ── Phase 2 (T2): reflexion re-entry, budget-bounded ──────────────────────────


def _failed_outcome():
    """A TaskOutcome with a 'failed' verdict and one unmet condition."""
    from components.schemas import TaskOutcome

    return TaskOutcome(
        outcome="failed",
        termination_clean=True,
        criteria_met=0.0,
        branch_coverage=0.0,
        unmet_conditions=["the migration is applied and reversible"],
        score=0.0,
        termination_reason="final_answer",
        goal_met=False,
    )


async def _run_reflexion(*, enabled: bool, max_attempts: int, tmp_path):
    """Drive a run whose every answer is judged 'failed'.

    With reflexion enabled, evaluate->reflect->route re-enters until the budget
    ceiling; the critique LLM and the answer LLM share the mocked ``ainvoke``, so
    we supply a long, repeating script (a final answer + a critique per pass).
    """
    from orchestration.react_loop import build_graph

    # Every answer is a no-tool final answer; the judge forces 'failed' so the
    # only thing that stops the loop is the reflexion budget.
    script = [_resp("Attempted but incomplete.", [], i) for i in range(40)]

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChat,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
        patch(
            "orchestration.react_loop.evaluate_task_outcome",
            return_value=_failed_outcome(),
        ),
    ):
        inst = MockChat.return_value
        inst.bind_tools.return_value = inst
        inst.ainvoke = AsyncMock(side_effect=script)

        graph = build_graph(
            agent_config=AgentConfig(
                default_model="gpt-4o-mini",
                models=[_fast_profile(), _capable_profile()],
                reflexion_enabled=enabled,
                max_reflexion_attempts=max_attempts,
            ),
            tool_registry=_registry(fail_first=False),
            cache_dir=tmp_path / "cache",
        )

        wf = f"wf-reflexion-{enabled}-{max_attempts}"
        return await graph.ainvoke(
            {
                "task_id": wf,
                "task_input": _TASK,
                "messages": [],
                "workflow_id": wf,
                "registered_agent_id": "sim-agent",
            },
            config={
                "configurable": {
                    "task_id": wf,
                    "user_id": "sim-user",
                    "workflow_id": wf,
                    "registered_agent_id": "sim-agent",
                }
            },
        )


@pytest.mark.asyncio
async def test_reflexion_loop_is_bounded_by_budget(tmp_path):
    """Thrash-bound (the D1 sim, P10): N reflexions hit the ceiling and stop.

    A failed verdict every pass would loop forever without the budget. With
    ``max_reflexion_attempts=2`` the loop terminates and ``reflections`` never
    exceeds the ceiling.
    """
    result = await _run_reflexion(enabled=True, max_attempts=2, tmp_path=tmp_path)
    reflections = result.get("reflections") or []
    assert 1 <= len(reflections) <= 2
    # Each critique is non-empty (the semantic gradient actually carried).
    assert all(r.get("critique", "").strip() for r in reflections)


@pytest.mark.asyncio
async def test_reflexion_disabled_never_reflects(tmp_path):
    """Control: with reflexion off, a failed verdict does NOT re-enter."""
    result = await _run_reflexion(enabled=False, max_attempts=2, tmp_path=tmp_path)
    assert (result.get("reflections") or []) == []


@pytest.mark.asyncio
async def test_reflexion_never_masks_failed_into_success(tmp_path):
    """Corrupt-success guard (Protocol-D3, stakeholder-legible): a reflexion
    loop never turns goal_met:false into a success — the FINAL outcome after
    the loop exhausts the budget is still 'failed'. YES/NO: NO masking."""
    result = await _run_reflexion(enabled=True, max_attempts=2, tmp_path=tmp_path)
    assert result.get("last_task_outcome") == "failed"
