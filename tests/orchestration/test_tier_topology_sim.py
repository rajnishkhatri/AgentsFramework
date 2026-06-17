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


# ── Step 0b (e2e-stress plan §2.2): trace carriers for Phases 2/3 ─────────────
# The escalation/reflexion facts must EXPORT to the BlackBox trace, or the
# downstream Langfuse analysis (analyze_planning_traces.py) is blind to exactly
# the loops it scores. We replay the recorded trace and assert the join keys
# land — counts/enums only, never critique text (§4.7 Recording).


def _replay_events(tmp_path, workflow_id: str):
    from services.governance.black_box import BlackBoxRecorder

    recorder = BlackBoxRecorder(
        storage_dir=tmp_path / "cache" / "black_box_recordings"
    )
    return recorder.replay(workflow_id)


@pytest.mark.asyncio
async def test_escalation_carrier_exports_on_reflexion_run(tmp_path):
    """Recording pillar: the TASK_COMPLETED event carries the escalation
    decision/reason and the budget counts, so the trace agrees with the route."""
    await _run_reflexion(enabled=True, max_attempts=2, tmp_path=tmp_path)
    events = _replay_events(tmp_path, "wf-reflexion-True-2")
    completed = [e for e in events if e.event_type.value == "task_completed"]
    assert completed, "no TASK_COMPLETED event recorded"
    last = completed[-1].details
    # Every key the analysis half reads is present.
    assert last["escalation_decision"] in ("reflect", "done")
    assert last["escalation_reason"] in (
        "verdict",
        "prose_repeat",
        "budget_exhausted",
        "clean",
        "disabled",
    )
    assert last["max_reflexion_attempts"] == 2
    assert isinstance(last["reflexion_attempt"], int)
    # A failed verdict that has exhausted the budget holds at the ceiling.
    assert last["escalation_reason"] == "budget_exhausted"
    assert last["escalation_decision"] == "done"
    # No critique text leaked onto the trace (Recording pillar).
    assert "critique" not in last


@pytest.mark.asyncio
async def test_reflexion_step_carrier_exports_per_reentry(tmp_path):
    """Each reflect_node re-entry records a STEP_PLANNED carrier with the
    attempt index and critique LENGTH (not text)."""
    await _run_reflexion(enabled=True, max_attempts=2, tmp_path=tmp_path)
    events = _replay_events(tmp_path, "wf-reflexion-True-2")
    reflexion_steps = [
        e.details
        for e in events
        if e.event_type.value == "step_planned"
        and "reflexion_attempt" in e.details
        and "reflexion_critique_chars" in e.details
    ]
    # The loop re-entered (1..2 times under the ceiling), one carrier each.
    assert 1 <= len(reflexion_steps) <= 2
    for d in reflexion_steps:
        assert isinstance(d["reflexion_attempt"], int)
        assert d["reflexion_critique_chars"] > 0  # gradient carried
        assert d["reflexion_unmet_count"] >= 1
        # counts only — the critique string itself is never on the trace.
        assert "critique" not in d


@pytest.mark.asyncio
async def test_disabled_run_records_escalation_reason_disabled(tmp_path):
    """Negative control: the live prod default (reflexion off) records
    escalation_reason='disabled' — the analysis can distinguish a held loop
    from a never-armed one (this is the deployed-revision signal)."""
    await _run_reflexion(enabled=False, max_attempts=2, tmp_path=tmp_path)
    events = _replay_events(tmp_path, "wf-reflexion-False-2")
    completed = [e for e in events if e.event_type.value == "task_completed"]
    assert completed
    assert completed[-1].details["escalation_reason"] == "disabled"
    assert completed[-1].details["escalation_decision"] == "done"
    # And no reflexion-step carriers were emitted (the loop never re-entered).
    reflexion_steps = [
        e for e in events
        if e.event_type.value == "step_planned" and "reflexion_attempt" in e.details
    ]
    assert reflexion_steps == []


# ══════════════════════════════════════════════════════════════════════════
# Phase 4 (T3): supervisor / worker / join fan-out topology sims.
#
# AP6 failure-first: every failure row (decline-identical, raise, timeout,
# all-fail, T2∘T3) is written BEFORE the single happy row. These are the tests
# that prove the fan-out is SAFE (plan §3.5a: MAST-bounded — one branch failing
# never erases survivors, never hangs, never corrupts the join). Mock the
# dispatcher + LLM (P6) — no live model. @pytest.mark.simulation (on-demand).
# ══════════════════════════════════════════════════════════════════════════

# A genuinely INDEPENDENT 3-branch plan (no sequencing markers → supervisor can
# fan out). The leading "Independently" keeps each step parallelizable.
_FANOUT_TASK = (
    "Independently summarize three unrelated documents: doc A, doc B, and doc C."
)

_INDEPENDENT_PLAN_JSON = json.dumps({
    "ordered_steps": [
        {"title": "A", "goal": "summarize document A"},
        {"title": "B", "goal": "summarize document B"},
        {"title": "C", "goal": "summarize document C"},
    ],
    "constraints": [],
    "success_conditions": ["all three documents are summarized"],
})

# A DEPENDENT plan (sequencing markers → supervisor must decline).
_DEPENDENT_PLAN_JSON = json.dumps({
    "ordered_steps": [
        {"title": "Fetch", "goal": "fetch the dataset from /workspace/raw.csv"},
        {"title": "Clean", "goal": "then clean the fetched data"},
        {"title": "Stat", "goal": "then compute the statistic from the cleaned data"},
    ],
    "constraints": [],
    "success_conditions": ["the statistic is computed"],
})

_DECOMPOSE_JSON = json.dumps({
    "branches": [
        {"objective": "summarize document A", "subagent_type": "general"},
        {"objective": "summarize document B", "subagent_type": "general"},
        {"objective": "summarize document C", "subagent_type": "general"},
    ]
})


def _make_branch_dispatch(behavior):
    """Patch target for LocalLLMDelegationDispatcher.dispatch_async.

    ``behavior`` maps an objective substring → one of: "ok" (succeed), "raise"
    (raise RuntimeError — the superstep-cancel hazard), "slow" (sleep past any
    timeout). Default is "ok".
    """
    async def _dispatch_async(self, request):  # noqa: ANN001
        objective = str(request.get("objective", ""))
        mode = "ok"
        for needle, m in behavior.items():
            if needle in objective:
                mode = m
                break
        if mode == "raise":
            raise RuntimeError(f"branch boom: {objective[:20]}")
        if mode == "slow":
            import asyncio as _a
            await _a.sleep(5.0)
        return {
            "status": "completed",
            "output": f"summary of: {objective[:40]}",
            "error": None,
            "child_correlation_id": f"{request.get('correlation_id')}:child:x",
            # Mirror the real dispatcher's usage surface (Step 5b / governance
            # Recording) so the worker STEP_EXECUTED carrier is non-zero.
            "usage": {
                "model": "gpt-4o-mini",
                "tokens_in": 33,
                "tokens_out": 11,
                "cost_usd": 0.0001,
                "latency_ms": 1.0,
            },
        }

    return _dispatch_async


async def _run_fanout(
    *,
    plan_json: str,
    branch_behavior: dict | None = None,
    tmp_path,
    workflow_id: str,
    reflexion_enabled: bool = False,
    branch_timeout_s: float = 60.0,
    extra_llm_after: int = 4,
):
    """Drive a fan-out run on the compiled graph (t3_fanout_enabled=True).

    LLM script order: [plan generator, supervisor decompose, join synthesis,
    then spare answers for evaluate/recap]. The dispatcher is patched per branch.
    """
    from orchestration.react_loop import build_graph

    script = [
        _resp(plan_json, [], 0),       # route_node plan generator (step 0)
        _resp(_DECOMPOSE_JSON, [], 1),  # supervisor_node decompose
    ] + [_resp(f"Joined / answered #{i}.", [], 10 + i) for i in range(extra_llm_after)]

    behavior = branch_behavior or {}

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChat,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
        patch(
            "services.tools.delegation_dispatcher.LocalLLMDelegationDispatcher.dispatch_async",
            _make_branch_dispatch(behavior),
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
                t3_fanout_enabled=True,
                reflexion_enabled=reflexion_enabled,
                max_reflexion_attempts=2,
                fanout_branch_timeout_s=branch_timeout_s,
            ),
            tool_registry=_registry(fail_first=False),
            cache_dir=tmp_path / "cache",
        )
        return await graph.ainvoke(
            {
                "task_id": workflow_id,
                "task_input": _FANOUT_TASK,
                "messages": [],
                "workflow_id": workflow_id,
                "registered_agent_id": "sim-agent",
            },
            config={
                "configurable": {
                    "task_id": workflow_id,
                    "user_id": "sim-user",
                    "workflow_id": workflow_id,
                    "registered_agent_id": "sim-agent",
                }
            },
        )


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_decline_is_identical_to_today(tmp_path):
    """THE REGRESSION CANARY: a DEPENDENT plan declines → no worker_results, the
    run completes via the normal call_llm path (byte-identical to the pre-T3
    spine for a non-fan-out task)."""
    result = await _run_fanout(
        plan_json=_DEPENDENT_PLAN_JSON,
        tmp_path=tmp_path,
        workflow_id="wf-fanout-decline",
    )
    # Declined: no branches ran, so worker_results stays empty.
    assert (result.get("worker_results") or []) == []
    # The supervisor recorded a decline decision carrier.
    events = _replay_events(tmp_path, "wf-fanout-decline")
    decisions = [
        e for e in events
        if e.event_type.value == "step_planned"
        and e.details.get("supervisor_decision")
    ]
    assert decisions and decisions[-1].details["supervisor_decision"] == "decline"
    assert "sequential-dependent" in decisions[-1].details["supervisor_reason"]


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_one_worker_raises_join_survives(tmp_path):
    """One branch raises → its sentinel is recorded, survivors are NOT erased,
    and the join synthesizes around the gap (superstep-cancel hazard guarded)."""
    result = await _run_fanout(
        plan_json=_INDEPENDENT_PLAN_JSON,
        branch_behavior={"document B": "raise"},
        tmp_path=tmp_path,
        workflow_id="wf-fanout-raise",
    )
    wr = result.get("worker_results") or []
    assert len(wr) == 3, "all three branches recorded (survivors + sentinel)"
    by_status = sorted(r["status"] for r in wr)
    assert by_status == ["completed", "completed", "failed"]
    failed = [r for r in wr if r["status"] == "failed"][0]
    assert failed["error"] and "boom" in failed["error"]


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_one_worker_times_out_no_hang(tmp_path):
    """One branch sleeps past the per-branch ceiling → asyncio.wait_for fires, a
    timeout sentinel is recorded, the other branches complete, no superstep hang."""
    result = await _run_fanout(
        plan_json=_INDEPENDENT_PLAN_JSON,
        branch_behavior={"document C": "slow"},
        branch_timeout_s=0.05,
        tmp_path=tmp_path,
        workflow_id="wf-fanout-timeout",
    )
    wr = result.get("worker_results") or []
    assert len(wr) == 3
    timed_out = [r for r in wr if r["status"] == "failed"]
    assert len(timed_out) == 1
    assert "timeout" in (timed_out[0]["error"] or "")


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_all_workers_fail_judge_still_runs(tmp_path):
    """All branches fail → the join still produces a NON-EMPTY degraded answer
    and the run reaches a terminal outcome (GTP-3: the judge always scores a
    non-empty joined answer — the corrupt-success guard holds)."""
    result = await _run_fanout(
        plan_json=_INDEPENDENT_PLAN_JSON,
        branch_behavior={"document A": "raise", "document B": "raise", "document C": "raise"},
        tmp_path=tmp_path,
        workflow_id="wf-fanout-allfail",
    )
    wr = result.get("worker_results") or []
    assert len(wr) == 3 and all(r["status"] == "failed" for r in wr)
    # The joined answer is non-empty (deterministic floor notes the gaps).
    assert (result.get("last_final_answer") or "").strip()
    # A terminal outcome was reached (the judge ran on the joined answer).
    assert result.get("last_task_outcome") in ("success", "partial", "failed")


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_composes_under_reflexion_budget(tmp_path):
    """T2∘T3: a fan-out run with reflexion enabled stays bounded — the supervisor
    re-runs on re-entry and the combined loop is capped by max_reflexion_attempts
    (one budget ceiling, no new knob)."""
    with patch(
        "orchestration.react_loop.evaluate_task_outcome",
        return_value=_failed_outcome(),
    ):
        result = await _run_fanout(
            plan_json=_INDEPENDENT_PLAN_JSON,
            tmp_path=tmp_path,
            workflow_id="wf-fanout-reflexion",
            reflexion_enabled=True,
            extra_llm_after=40,
        )
    # The reflexion loop is bounded by the budget even with the fan-out fork.
    assert len(result.get("reflections") or []) <= 2


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_happy_path_all_succeed(tmp_path):
    """The ONE acceptance (written last): all branches succeed → join → evaluate
    → terminal. Per-branch delegation_requested carriers landed on the trace."""
    result = await _run_fanout(
        plan_json=_INDEPENDENT_PLAN_JSON,
        tmp_path=tmp_path,
        workflow_id="wf-fanout-happy",
    )
    wr = result.get("worker_results") or []
    assert len(wr) == 3 and all(r["status"] == "completed" for r in wr)
    assert (result.get("last_final_answer") or "").strip()
    # GTP-1: a delegation_requested carrier per branch landed (BlackBox fallback,
    # since the sim wires no trace_service).
    events = _replay_events(tmp_path, "wf-fanout-happy")
    requested = [
        e for e in events
        if e.details.get("delegation_event") == "delegation_requested"
    ]
    assert len(requested) == 3


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_path_emits_step_executed_token_carriers(tmp_path):
    """Governance Recording pillar (audit 6d12ba69 Finding 2): the fan-out path
    bypasses call_llm, so each of its LLM calls (supervisor decompose, N workers,
    join synthesis) must emit its OWN STEP_EXECUTED — else branch tokens/cost are
    invisible in the governance trace. Asserts a STEP_EXECUTED carrier per source
    with non-null token fields. The sim dispatch surfaces ``usage`` (mirroring the
    real dispatcher; Step 5b) so the worker carriers are non-zero."""
    await _run_fanout(
        plan_json=_INDEPENDENT_PLAN_JSON,
        tmp_path=tmp_path,
        workflow_id="wf-fanout-stepexec",
    )

    events = _replay_events(tmp_path, "wf-fanout-stepexec")
    step_exec = [e for e in events if e.event_type.value == "step_executed"]
    by_source: dict[str, list] = {}
    for e in step_exec:
        by_source.setdefault(e.details.get("source", "call_llm"), []).append(e.details)

    # One supervisor + three workers + one join carrier, each with tokens.
    assert len(by_source.get("fanout_supervisor", [])) == 1
    assert len(by_source.get("fanout_worker", [])) == 3
    assert len(by_source.get("fanout_join", [])) == 1
    for src in ("fanout_supervisor", "fanout_worker", "fanout_join"):
        for d in by_source[src]:
            # the carrier exists AND carries real token fields (not None/absent)
            assert d.get("tokens_in") is not None
            assert d.get("tokens_out") is not None
            assert d.get("cost_usd") is not None
    # worker tokens came through the dispatcher usage surface (non-zero).
    assert all(d["tokens_in"] == 33 for d in by_source["fanout_worker"])


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_supervisor_logs_phaselogger_decision(tmp_path):
    """Governance Reasoning pillar (audit 6d12ba69 Finding C): the supervisor's
    fan_out|decline choice must reach the PhaseLogger ``decisions.jsonl`` sink
    AND its black_box ``step.planned`` carrier, joined by ``decision_id`` — the
    canonical 'same data, two sinks' rationale idiom (mirrors MODEL_SELECTED).
    Before the fix the decision lived in only one sink (step.planned)."""
    from services.governance.phase_logger import PhaseLogger

    await _run_fanout(
        plan_json=_INDEPENDENT_PLAN_JSON,
        tmp_path=tmp_path,
        workflow_id="wf-fanout-decision",
    )

    # PhaseLogger sink: a decision row carrying the fan-out rationale.
    pl = PhaseLogger(storage_dir=tmp_path / "cache" / "phase_logs")
    decisions = pl.export_workflow_log("wf-fanout-decision")
    sup_decisions = [
        d for d in decisions
        if "fan_out" in str(d.get("description", "")).lower()
        or "decline" in str(d.get("description", "")).lower()
    ]
    assert sup_decisions, "supervisor logged no PhaseLogger Decision row"
    sup = sup_decisions[-1]
    assert sup.get("rationale"), "decision row missing rationale"
    assert sup.get("decision_id"), "decision row missing decision_id"

    # black_box sink: the step.planned carrier shares the SAME decision_id.
    events = _replay_events(tmp_path, "wf-fanout-decision")
    sup_planned = [
        e for e in events
        if e.event_type.value == "step_planned"
        and "supervisor_decision" in e.details
    ]
    assert sup_planned, "no supervisor step.planned carrier"
    assert sup_planned[-1].details.get("decision_id") == sup["decision_id"], (
        "step.planned and decisions.jsonl carry different decision_id — "
        "the two sinks are not joinable"
    )


@pytest.mark.simulation
@pytest.mark.asyncio
async def test_fanout_is_not_memory_blind(tmp_path):
    """Phase 1 memory, T3 tier: the fan-out path bypasses call_llm, so recall
    runs in route_node (the universal seam). Assert the recalled block reaches
    the supervisor decompose prompt — a fan-out run must NOT be memory-blind —
    and that recall ran exactly once for the run (route, not per worker)."""
    from orchestration.react_loop import build_graph
    from services.long_term_memory import (
        InMemoryMemoryBackend,
        LongTermMemoryService,
    )

    service = LongTermMemoryService(InMemoryMemoryBackend())
    # InMemoryMemoryBackend.search matches `query in repr(payload)`, and the
    # query is the FULL task_input (route_node passes task_input as the query).
    # So embed the whole task string in the seed payload, alongside a recognizable
    # marker the assertion looks for in the prompt.
    service.store(
        "sim-user",
        "seed",
        {"text": f"user prefers terse document summaries [{_FANOUT_TASK}]"},
    )

    captured: list = []
    script = [
        _resp(_INDEPENDENT_PLAN_JSON, [], 0),  # route_node plan generator
        _resp(_DECOMPOSE_JSON, [], 1),          # supervisor decompose
    ] + [_resp(f"Joined #{i}.", [], 10 + i) for i in range(4)]

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockChat,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
        patch(
            "services.tools.delegation_dispatcher.LocalLLMDelegationDispatcher.dispatch_async",
            _make_branch_dispatch({}),
        ),
    ):
        inst = MockChat.return_value
        inst.bind_tools.return_value = inst

        async def _ainvoke(messages, *a, **k):
            captured.append(messages)
            return script[min(len(captured) - 1, len(script) - 1)]

        inst.ainvoke = AsyncMock(side_effect=_ainvoke)

        graph = build_graph(
            agent_config=AgentConfig(
                default_model="gpt-4o-mini",
                models=[_fast_profile(), _capable_profile()],
                plan_source="generated",
                t3_fanout_enabled=True,
                memory_enabled=True,
            ),
            tool_registry=_registry(fail_first=False),
            cache_dir=tmp_path / "cache",
            memory_service=service,
        )
        result = await graph.ainvoke(
            {
                "task_id": "wf-fanout-mem",
                "task_input": _FANOUT_TASK,
                "messages": [],
                "workflow_id": "wf-fanout-mem",
                "registered_agent_id": "sim-agent",
                "user_id": "sim-user",
            },
            config={
                "configurable": {
                    "task_id": "wf-fanout-mem",
                    "user_id": "sim-user",
                    "workflow_id": "wf-fanout-mem",
                }
            },
        )

    # The run completed via the fan-out path.
    assert "messages" in result
    # The supervisor decompose call (LLM call #2) carried the recalled block in
    # its user message — proof the fan-out run saw memory.
    all_text = " ".join(
        str(getattr(m, "content", m))
        for batch in captured
        for m in batch
    )
    assert "terse document summaries" in all_text, (
        "the recalled memory never reached any fan-out prompt — memory-blind"
    )
    # Recall queried the backend exactly once for the whole run (route seam,
    # memoized — not once per worker / supervisor re-entry).
    events = _replay_events(tmp_path, "wf-fanout-mem")
    recalled = [e for e in events if e.event_type.value == "memory_recalled"]
    assert len(recalled) == 1, f"expected one recall carrier, got {len(recalled)}"
