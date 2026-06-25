"""L4 Behavioral: TaskUnderstanding generation wiring in react_loop (Phase 2).

Failure-mode matrix (task_understanding plan §5 Phase 2, Pattern 11):
{flag deterministic, shadow, generated+ok, generated+raise, generated+gate-reject}
— every cell asserts which conditions the GoalJudge received and the
``conditions_source`` recorded in the eval telemetry. Rejection/fallback cells
are tested before the acceptance cell (TAP-4).

Governance recording (plan §4.7): STEP_PLANNED details carry
``conditions_source``/``plan_ref``/``decision_id``; a ROUTING-phase Decision
with the matching ``decision_id`` explains WHY this run used generated vs
deterministic conditions; gate rejection emits GUARDRAIL_CHECKED; the
black-box hash chain stays valid across the new events.

Mocked LLM throughout — the generator is patched at the orchestration import
site so its behaviour is the controlled input dimension.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from components.schemas import GoalVerdict, TaskUnderstanding
from components.task_understanding import TaskUnderstandingValidationError
from services import eval_telemetry
from services.base_config import AgentConfig, ModelProfile
from services.goal_judge_runtime_config import InMemoryGoalJudgeConfigReader

_TASK = "Compare options. Evaluate risks. Propose migration."

# The generator no longer appends the generic consistency tail at plan-time
# (it moved to judge-time). This fixture mirrors what generate() now returns:
# task-specific conditions only.
_GENERATED = TaskUnderstanding(
    restated_intent="Compare the options, evaluate their risks, and propose a migration.",
    success_conditions=[
        "The answer compares the available options.",
        "The answer evaluates risks of each option.",
        "The answer proposes a migration path.",
    ],
    confidence=0.9,
    source="generated",
    model="gpt-4o-mini",
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


class _RecordingSink:
    """In-memory EvalTelemetrySink capturing both observation kinds."""

    def __init__(self) -> None:
        self.goal_judge: list[dict[str, Any]] = []
        self.task_understanding: list[dict[str, Any]] = []

    def publish_goal_judge(self, **kwargs: Any) -> None:
        self.goal_judge.append(kwargs)

    def publish_task_understanding(self, **kwargs: Any) -> None:
        self.task_understanding.append(kwargs)


@pytest.fixture(autouse=True)
def _sink():
    sink = _RecordingSink()
    eval_telemetry.set_sink(sink)
    yield sink
    eval_telemetry.set_sink(None)


def _events(tmp_path, workflow_id: str) -> list[dict]:
    trace_file = (
        tmp_path / "cache" / "black_box_recordings" / workflow_id / "trace.jsonl"
    )
    return [json.loads(ln) for ln in trace_file.read_text().splitlines() if ln]


def _decisions(tmp_path, workflow_id: str) -> list[dict]:
    log = tmp_path / "cache" / "phase_logs" / workflow_id / "decisions.jsonl"
    if not log.exists():
        return []
    return [json.loads(ln) for ln in log.read_text().splitlines() if ln]


async def _run(
    tmp_path,
    *,
    workflow_id: str,
    conditions_source: str,
    generate: AsyncMock,
    judge: AsyncMock | None = None,
    task_input: str = _TASK,
) -> dict[str, Any]:
    """Drive the graph to completion; return observability handles."""
    mock_response = MagicMock()
    mock_response.content = "FINAL ANSWER: comparison, risks, and migration plan."
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
    mock_response.response_metadata = {"model_name": "gpt-4o-mini"}

    judge = judge or AsyncMock(
        return_value=GoalVerdict(goal_met=True, criteria_met=1.0)
    )
    reader = InMemoryGoalJudgeConfigReader(
        goal_judge_enabled=True,
        goal_judge_downgrade_enabled=False,
        success_conditions_source=conditions_source,  # type: ignore[arg-type]
    )

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockLLM,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
        patch("orchestration.react_loop.GoalJudge.evaluate", judge),
        patch(
            "orchestration.react_loop.TaskUnderstandingGenerator.generate",
            generate,
        ),
    ):
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)

        from orchestration.react_loop import build_graph

        graph = build_graph(
            agent_config=AgentConfig(
                default_model="gpt-4o-mini",
                models=[_fast_profile()],
                goal_judge_enabled=True,
            ),
            cache_dir=tmp_path / "cache",
            goal_judge_config_reader=reader,
        )
        await graph.ainvoke(
            {
                "task_id": "t",
                "task_input": task_input,
                "messages": [],
                "workflow_id": workflow_id,
            },
            config={"configurable": {"task_id": "t", "user_id": "u"}},
        )

    return {"judge": judge, "generate": generate}


def _judge_conditions(judge: AsyncMock) -> list[str]:
    return judge.call_args.kwargs["success_conditions"]


# ─────────────────────────────────────────────────────────────────────
# Failure-mode matrix — fallback/rejection cells FIRST (TAP-4)
# ─────────────────────────────────────────────────────────────────────


class TestFailureModeMatrix:
    @pytest.mark.asyncio
    async def test_flag_deterministic_never_calls_generator(self, tmp_path, _sink):
        generate = AsyncMock(return_value=_GENERATED)
        handles = await _run(
            tmp_path,
            workflow_id="wf-tu-det",
            conditions_source="deterministic",
            generate=generate,
        )
        assert generate.await_count == 0
        conditions = _judge_conditions(handles["judge"])
        assert any("Compare options" in c for c in conditions)
        gj = _sink.goal_judge[0]
        assert gj["ai_input"]["conditions_source"] == "deterministic"

    @pytest.mark.asyncio
    async def test_generator_exception_falls_back_to_deterministic(
        self, tmp_path, _sink
    ):
        generate = AsyncMock(side_effect=RuntimeError("provider down"))
        handles = await _run(
            tmp_path,
            workflow_id="wf-tu-raise",
            conditions_source="generated",
            generate=generate,
        )
        assert generate.await_count == 1
        conditions = _judge_conditions(handles["judge"])
        assert any("Compare options" in c for c in conditions)
        assert _sink.goal_judge[0]["ai_input"]["conditions_source"] == "deterministic"
        # A transport raise on the first attempt is 1 attempt made, with no
        # rejected text to archive (bug-#1 accounting on the non-gate path).
        tu = _sink.task_understanding[0]["ai_response"]
        assert tu["attempts"] == 1
        assert tu["rejected_conditions"] == []
        # Reasoning pillar: the fallback Decision names the failure class.
        decisions = [
            d for d in _decisions(tmp_path, "wf-tu-raise")
            if "success-conditions" in d.get("description", "")
        ]
        assert len(decisions) == 1
        assert "RuntimeError" in decisions[0]["rationale"]

    @pytest.mark.asyncio
    async def test_gate_rejection_falls_back_and_records_guardrail_per_attempt(
        self, tmp_path, _sink
    ):
        """Round 2: the generator retries once on a gate rejection and fires
        ``on_gate_rejection`` per rejected attempt. Both attempts ungrounded →
        TWO GUARDRAIL_CHECKED events (attempt 0 and 1), then raise → fallback
        to the deterministic floor.

        R3 telemetry fixes asserted here: every rejected attempt's condition
        TEXT is archived in the guardrail event and the eval record (bug #2 —
        round 2's root cause was mis-diagnosed because the text was never
        captured), and ``attempts`` reports the attempts actually MADE — a
        2-attempt terminal fallback is 2, not 3 (bug #1 off-by-one)."""
        _issues = ["grounding gate: condition 1 shares no content token with the task input"]
        _rejected = [
            ["The agent does the thing.", "Zorblat frequencies harmonized."],
            ["The agent does the thing.", "Quantum flux capacitors aligned."],
        ]

        async def _reject_both(*, task_input, on_gate_rejection=None):
            # The real generator calls the callback for each rejected attempt
            # with that attempt's rejected condition text.
            if on_gate_rejection is not None:
                on_gate_rejection(_issues, 0, _rejected[0])
                on_gate_rejection(_issues, 1, _rejected[1])
            raise TaskUnderstandingValidationError([*_issues, *_issues])

        generate = AsyncMock(side_effect=_reject_both)
        handles = await _run(
            tmp_path,
            workflow_id="wf-tu-gate",
            conditions_source="generated",
            generate=generate,
        )
        conditions = _judge_conditions(handles["judge"])
        assert any("Compare options" in c for c in conditions)
        assert _sink.goal_judge[0]["ai_input"]["conditions_source"] == "deterministic"
        # Validation pillar: each rejected attempt is its own GUARDRAIL_CHECKED
        # event, carrying the attempt index, the failing gate name, and the
        # rejected condition text itself.
        guardrails = [
            e for e in _events(tmp_path, "wf-tu-gate")
            if e["event_type"] == "guardrail_checked"
            and e["details"].get("guardrail") == "task_understanding_gates"
        ]
        assert len(guardrails) == 2
        assert {g["details"]["attempt"] for g in guardrails} == {0, 1}
        assert all(g["details"]["passed"] is False for g in guardrails)
        assert all("grounding" in str(g["details"]["issues"]) for g in guardrails)
        assert [g["details"]["conditions"] for g in guardrails] == _rejected
        # Eval record: terminal fallback after 2 rejected attempts → attempts
        # is exactly 2 (bug #1), and the rejected text rides along (bug #2) so
        # future rounds can be re-simulated offline without regeneration.
        tu = _sink.task_understanding[0]["ai_response"]
        assert tu["attempts"] == 2
        assert [r["conditions"] for r in tu["rejected_conditions"]] == _rejected

    @pytest.mark.asyncio
    async def test_gate_rejection_then_retry_recovers_consumes_generated(
        self, tmp_path, _sink
    ):
        """Round 2: attempt 0 rejected, attempt 1 recovers → judge consumes the
        GENERATED conditions; exactly ONE GUARDRAIL_CHECKED (attempt 0); the
        Decision rationale records the retry recovery; ``attempts`` counts the
        rejected attempt plus the recovery (= 2)."""
        _issues = ["grounding gate: condition 1 shares no content token with the task input"]
        _rejected0 = ["The agent compares options.", "Zorblat frequencies harmonized."]

        async def _reject_then_recover(*, task_input, on_gate_rejection=None):
            if on_gate_rejection is not None:
                on_gate_rejection(_issues, 0, _rejected0)
            return _GENERATED

        generate = AsyncMock(side_effect=_reject_then_recover)
        handles = await _run(
            tmp_path,
            workflow_id="wf-tu-retry",
            conditions_source="generated",
            generate=generate,
        )
        # The recovered (generated) conditions reach the judge.
        assert _judge_conditions(handles["judge"]) == _GENERATED.success_conditions
        assert _sink.goal_judge[0]["ai_input"]["conditions_source"] == "generated"
        # Exactly one rejected attempt → one GUARDRAIL_CHECKED (attempt 0).
        guardrails = [
            e for e in _events(tmp_path, "wf-tu-retry")
            if e["event_type"] == "guardrail_checked"
            and e["details"].get("guardrail") == "task_understanding_gates"
        ]
        assert len(guardrails) == 1
        assert guardrails[0]["details"]["attempt"] == 0
        assert guardrails[0]["details"]["conditions"] == _rejected0
        # Recovery after one rejection = 2 attempts made; the rejected text
        # from attempt 0 is archived alongside the consumed artifact.
        tu = _sink.task_understanding[0]["ai_response"]
        assert tu["attempts"] == 2
        assert [r["conditions"] for r in tu["rejected_conditions"]] == [_rejected0]
        # Reasoning pillar: the Decision rationale flags the retry recovery.
        decisions = [
            d for d in _decisions(tmp_path, "wf-tu-retry")
            if "success-conditions" in d.get("description", "")
        ]
        assert len(decisions) == 1
        assert "retry" in decisions[0]["rationale"].lower()

    @pytest.mark.asyncio
    async def test_shadow_generates_but_judge_consumes_deterministic(
        self, tmp_path, _sink
    ):
        """Stage 2a: generate + validate + publish, judge still scores the
        deterministic floor."""
        generate = AsyncMock(return_value=_GENERATED)
        handles = await _run(
            tmp_path,
            workflow_id="wf-tu-shadow",
            conditions_source="shadow",
            generate=generate,
        )
        assert generate.await_count == 1
        conditions = _judge_conditions(handles["judge"])
        assert any("Compare options" in c for c in conditions)
        assert _sink.goal_judge[0]["ai_input"]["conditions_source"] == "deterministic"
        # The shadow artifact is still published for calibration.
        assert len(_sink.task_understanding) == 1
        tu = _sink.task_understanding[0]["ai_response"]
        assert tu["source"] == "generated"

    # ── acceptance cell ──

    @pytest.mark.asyncio
    async def test_generated_consumed_by_judge_and_telemetry(self, tmp_path, _sink):
        generate = AsyncMock(return_value=_GENERATED)
        handles = await _run(
            tmp_path,
            workflow_id="wf-tu-on",
            conditions_source="generated",
            generate=generate,
        )
        assert _judge_conditions(handles["judge"]) == _GENERATED.success_conditions
        gj = _sink.goal_judge[0]["ai_input"]
        assert gj["conditions_source"] == "generated"
        assert gj["restated_intent"] == _GENERATED.restated_intent
        assert gj["success_conditions"] == _GENERATED.success_conditions


# ─────────────────────────────────────────────────────────────────────
# Memoization — route_node re-runs every loop iteration
# ─────────────────────────────────────────────────────────────────────


class TestMemoization:
    @pytest.mark.asyncio
    async def test_multi_iteration_run_generates_exactly_once(self, tmp_path):
        """evaluate→continue→route re-enters route_node; generation must be
        memoized on the ``task_understanding`` state key (plan §3 seam)."""
        from pydantic import BaseModel

        from services.tools.registry import ToolDefinition, ToolRegistry

        class _EchoInput(BaseModel):
            text: str

        registry = ToolRegistry({
            "echo": ToolDefinition(
                executor=lambda args: str(args.get("text", "")),
                schema=_EchoInput,
                cacheable=False,
            )
        })

        def _resp(content: str, tool_calls: list[dict], idx: int) -> MagicMock:
            r = MagicMock()
            r.content = content
            r.tool_calls = [
                {"name": tc["name"], "args": tc["args"],
                 "id": f"tc-{idx}-{p}", "type": "tool_call"}
                for p, tc in enumerate(tool_calls)
            ]
            r.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
            r.response_metadata = {"model_name": "gpt-4o-mini"}
            return r

        responses = [
            _resp("", [{"name": "echo", "args": {"text": "ping"}}], 0),
            _resp("", [{"name": "echo", "args": {"text": "pong"}}], 1),
            _resp("FINAL ANSWER: done after two tool rounds.", [], 2),
        ]

        generate = AsyncMock(return_value=_GENERATED)
        reader = InMemoryGoalJudgeConfigReader(
            goal_judge_enabled=False,
            success_conditions_source="generated",
        )

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
            patch(
                "orchestration.react_loop.TaskUnderstandingGenerator.generate",
                generate,
            ),
        ):
            llm = MockLLM.return_value
            llm.bind_tools.return_value = llm
            llm.ainvoke = AsyncMock(side_effect=responses)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=AgentConfig(
                    default_model="gpt-4o-mini",
                    models=[_fast_profile()],
                ),
                tool_registry=registry,
                cache_dir=tmp_path / "cache",
                goal_judge_config_reader=reader,
            )
            result = await graph.ainvoke(
                {
                    "task_id": "t",
                    "task_input": _TASK,
                    "messages": [],
                    "workflow_id": "wf-tu-memo",
                },
                config={"configurable": {"task_id": "t", "user_id": "u"}},
            )

        assert result["step_count"] >= 2  # the loop actually iterated
        assert generate.await_count == 1  # but generation fired once
        # State carries the memoized artifact end-to-end.
        assert result["task_understanding"]["source"] == "generated"


# ─────────────────────────────────────────────────────────────────────
# Cross-turn regeneration — thread state outlives the turn
# ─────────────────────────────────────────────────────────────────────


class TestCrossTurnRegeneration:
    @pytest.mark.asyncio
    async def test_new_turn_regenerates_and_judge_consumes_fresh_conditions(
        self, tmp_path, _sink
    ):
        """Cross-turn staleness (governance audit 3921c61b, 2026-06-12): the
        ``task_understanding`` state key persists across runs via the
        checkpointer while ``task_id`` is minted per turn, so without a task
        binding the turn-2 judge consumes turn-1's conditions (live false
        verdict: criteria_met 0.0 on a healthy run). Each new turn must
        regenerate and be judged against ITS OWN task's conditions."""
        from langgraph.checkpoint.memory import MemorySaver

        task_1 = "Compare options. Evaluate risks. Propose migration."
        task_2 = "Summarize the risk register and name the top risk."
        turn_1 = _GENERATED
        turn_2 = TaskUnderstanding(
            restated_intent="Summarize the risk register, naming the top risk.",
            success_conditions=[
                "The answer summarizes the risk register.",
                "The answer names the top risk explicitly.",
            ],
            confidence=0.9,
            source="generated",
            model="gpt-4o-mini",
        )

        def _resp() -> MagicMock:
            r = MagicMock()
            r.content = "FINAL ANSWER: done."
            r.tool_calls = []
            r.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
            r.response_metadata = {"model_name": "gpt-4o-mini"}
            return r

        generate = AsyncMock(side_effect=[turn_1, turn_2])
        judge = AsyncMock(
            return_value=GoalVerdict(goal_met=True, criteria_met=1.0)
        )
        reader = InMemoryGoalJudgeConfigReader(
            goal_judge_enabled=True,
            goal_judge_downgrade_enabled=False,
            success_conditions_source="generated",
        )

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
            patch("orchestration.react_loop.GoalJudge.evaluate", judge),
            patch(
                "orchestration.react_loop.TaskUnderstandingGenerator.generate",
                generate,
            ),
        ):
            MockLLM.return_value.ainvoke = AsyncMock(side_effect=_resp)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=AgentConfig(
                    default_model="gpt-4o-mini",
                    models=[_fast_profile()],
                    goal_judge_enabled=True,
                ),
                cache_dir=tmp_path / "cache",
                checkpointer=MemorySaver(),
                goal_judge_config_reader=reader,
            )
            # Turn 1 and turn 2 on the SAME thread — fresh task_id each, the
            # runtime adapter's per-run contract (langgraph_runtime.run()).
            for task_id, task_input, wf in (
                ("task-1", task_1, "wf-tu-turn-1"),
                ("task-2", task_2, "wf-tu-turn-2"),
            ):
                await graph.ainvoke(
                    {
                        "task_id": task_id,
                        "task_input": task_input,
                        "messages": [],
                        "workflow_id": wf,
                    },
                    config={"configurable": {
                        "thread_id": "thread-multi-turn",
                        "task_id": task_id,
                        "user_id": "u",
                    }},
                )

        # Generation fired once PER TURN (not once per thread).
        assert generate.await_count == 2
        # Each turn's judge consumed that turn's conditions — turn 2 must NOT
        # be scored against turn 1's checklist.
        assert judge.await_count == 2
        first_call, second_call = judge.call_args_list
        assert first_call.kwargs["success_conditions"] == turn_1.success_conditions
        assert second_call.kwargs["success_conditions"] == turn_2.success_conditions
        # Shadow/consume telemetry published per turn.
        assert len(_sink.task_understanding) == 2
        assert (
            _sink.task_understanding[1]["ai_response"]["restated_intent"]
            == turn_2.restated_intent
        )


# ─────────────────────────────────────────────────────────────────────
# Governance recording (§4.7) — Recording + Reasoning pillars
# ─────────────────────────────────────────────────────────────────────


class TestGovernanceRecording:
    @pytest.mark.asyncio
    async def test_step_planned_carries_join_keys_and_decision_matches(
        self, tmp_path
    ):
        generate = AsyncMock(return_value=_GENERATED)
        await _run(
            tmp_path,
            workflow_id="wf-tu-gov",
            conditions_source="generated",
            generate=generate,
        )
        events = _events(tmp_path, "wf-tu-gov")
        planned = [e for e in events if e["event_type"] == "step_planned"]
        assert planned, "expected a STEP_PLANNED event"
        details = planned[0]["details"]
        assert details["conditions_source"] == "generated"
        assert details["plan_ref"].startswith(".agent_plans/")
        decision_id = details["decision_id"]
        assert decision_id
        # Cross-pillar join: the decision_id resolves to a ROUTING Decision.
        decisions = [
            d for d in _decisions(tmp_path, "wf-tu-gov")
            if d.get("decision_id") == decision_id
        ]
        assert len(decisions) == 1
        assert "success-conditions" in decisions[0]["description"]
        assert decisions[0]["confidence"] == pytest.approx(_GENERATED.confidence)

    @pytest.mark.asyncio
    async def test_hash_chain_valid_across_new_events(self, tmp_path):
        generate = AsyncMock(
            side_effect=TaskUnderstandingValidationError(["count gate: got 1"])
        )
        await _run(
            tmp_path,
            workflow_id="wf-tu-chain",
            conditions_source="generated",
            generate=generate,
        )
        from services.governance.black_box import BlackBoxRecorder

        recorder = BlackBoxRecorder(
            storage_dir=tmp_path / "cache" / "black_box_recordings"
        )
        bundle = recorder.export("wf-tu-chain")
        assert bundle["hash_chain_valid"] is True

    @pytest.mark.asyncio
    async def test_eval_task_understanding_published_with_provenance(
        self, tmp_path, _sink
    ):
        generate = AsyncMock(return_value=_GENERATED)
        await _run(
            tmp_path,
            workflow_id="wf-tu-eval",
            conditions_source="generated",
            generate=generate,
        )
        assert len(_sink.task_understanding) == 1
        record = _sink.task_understanding[0]
        assert record["trace_id"] == "wf-tu-eval"
        assert record["ai_response"]["source"] == "generated"
        assert record["ai_response"]["restated_intent"] == _GENERATED.restated_intent
        assert record["model"] == "gpt-4o-mini"
        # First-attempt success: exactly 1 attempt, nothing rejected.
        assert record["ai_response"]["attempts"] == 1
        assert record["ai_response"]["rejected_conditions"] == []


# ─────────────────────────────────────────────────────────────────────
# Phase 4 — pause → edit → resume simulation (Pattern 10)
# ─────────────────────────────────────────────────────────────────────


class TestEditResumeSimulation:
    @pytest.mark.asyncio
    async def test_user_edit_at_interrupt_reaches_judge_and_telemetry(
        self, tmp_path, _sink
    ):
        """Mocked LLM, real in-memory checkpointer: run pauses at the
        execute_tool interrupt, the artifact is edited via update_state
        (what the middleware endpoint does through the runtime adapter),
        the run resumes with None input, and the terminal judge + telemetry
        see ``conditions_source="user_edited"`` with the edited text."""
        from langgraph.checkpoint.memory import MemorySaver
        from pydantic import BaseModel

        from services.tools.registry import ToolDefinition, ToolRegistry

        class _EchoInput(BaseModel):
            text: str

        registry = ToolRegistry({
            "echo": ToolDefinition(
                executor=lambda args: str(args.get("text", "")),
                schema=_EchoInput,
                cacheable=False,
            )
        })

        def _resp(content: str, tool_calls: list[dict], idx: int) -> MagicMock:
            r = MagicMock()
            r.content = content
            r.tool_calls = [
                {"name": tc["name"], "args": tc["args"],
                 "id": f"tc-{idx}-{p}", "type": "tool_call"}
                for p, tc in enumerate(tool_calls)
            ]
            r.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
            r.response_metadata = {"model_name": "gpt-4o-mini"}
            return r

        responses = [
            _resp("", [{"name": "echo", "args": {"text": "ping"}}], 0),
            _resp("FINAL ANSWER: compared options and proposed the migration.", [], 1),
        ]

        judge = AsyncMock(return_value=GoalVerdict(goal_met=True, criteria_met=1.0))
        generate = AsyncMock(return_value=_GENERATED)
        reader = InMemoryGoalJudgeConfigReader(
            goal_judge_enabled=True,
            success_conditions_source="generated",
        )

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
            patch("orchestration.react_loop.GoalJudge.evaluate", judge),
            patch(
                "orchestration.react_loop.TaskUnderstandingGenerator.generate",
                generate,
            ),
        ):
            llm = MockLLM.return_value
            llm.bind_tools.return_value = llm
            llm.ainvoke = AsyncMock(side_effect=responses)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=AgentConfig(
                    default_model="gpt-4o-mini",
                    models=[_fast_profile()],
                    goal_judge_enabled=True,
                ),
                tool_registry=registry,
                cache_dir=tmp_path / "cache",
                checkpointer=MemorySaver(),
                goal_judge_config_reader=reader,
                interrupt_before_execute_tool=True,
            )
            config = {
                "configurable": {
                    "thread_id": "thread-edit",
                    "task_id": "t",
                    "user_id": "u",
                }
            }
            await graph.ainvoke(
                {
                    "task_id": "t",
                    "task_input": _TASK,
                    "messages": [],
                    "workflow_id": "wf-tu-edit",
                },
                config=config,
            )
            # Paused at the execute_tool interrupt with the generated artifact.
            snapshot = await graph.aget_state(config)
            assert snapshot.next, "expected the run to pause at execute_tool"
            assert snapshot.values["task_understanding"]["source"] == "generated"

            edited = {
                **snapshot.values["task_understanding"],
                "restated_intent": "Only compare the options.",
                "success_conditions": [
                    "The answer compares the available options.",
                    "The comparison is grounded in the task text.",
                ],
                "source": "user_edited",
            }
            await graph.aupdate_state(config, {"task_understanding": edited})

            # Resume with None input (the canonical checkpoint resume).
            await graph.ainvoke(None, config=config)

        assert judge.await_count == 1
        assert _judge_conditions(judge) == edited["success_conditions"]
        gj = _sink.goal_judge[0]["ai_input"]
        assert gj["conditions_source"] == "user_edited"
        assert gj["restated_intent"] == "Only compare the options."

    @pytest.mark.asyncio
    async def test_full_runtime_stream_pause_edit_resume(self, tmp_path, _sink):
        """Same scenario driven through ``LangGraphRuntime`` end to end:
        the first ``run()`` pauses at the interrupt, the edit goes through
        ``update_task_understanding`` (what the middleware endpoint calls),
        and the resume leg is ``run(input={"_resume": True})`` — asserting
        the resumed stream keeps the original trace_id, re-emits the
        user_edited card, and the judge scores the edited conditions."""
        from langgraph.checkpoint.memory import MemorySaver
        from pydantic import BaseModel

        from agent_ui_adapter.adapters.runtime.langgraph_runtime import (
            LangGraphRuntime,
        )
        from agent_ui_adapter.wire.domain_events import (
            RunStartedDomain,
            TaskUnderstood,
        )
        from services.tools.registry import ToolDefinition, ToolRegistry
        from trust.models import AgentFacts

        class _EchoInput(BaseModel):
            text: str

        registry = ToolRegistry({
            "echo": ToolDefinition(
                executor=lambda args: str(args.get("text", "")),
                schema=_EchoInput,
                cacheable=False,
            )
        })

        def _resp(content: str, tool_calls: list[dict], idx: int) -> MagicMock:
            r = MagicMock()
            r.content = content
            r.tool_calls = [
                {"name": tc["name"], "args": tc["args"],
                 "id": f"tc-{idx}-{p}", "type": "tool_call"}
                for p, tc in enumerate(tool_calls)
            ]
            r.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
            r.response_metadata = {"model_name": "gpt-4o-mini"}
            return r

        responses = [
            _resp("", [{"name": "echo", "args": {"text": "ping"}}], 0),
            _resp("FINAL ANSWER: compared options and proposed the migration.", [], 1),
        ]

        judge = AsyncMock(return_value=GoalVerdict(goal_met=True, criteria_met=1.0))
        generate = AsyncMock(return_value=_GENERATED)
        reader = InMemoryGoalJudgeConfigReader(
            goal_judge_enabled=True,
            success_conditions_source="generated",
        )
        identity = AgentFacts(
            agent_id="a1", agent_name="Bot", owner="team", version="1.0.0"
        )

        with (
            patch("langchain_litellm.ChatLiteLLM") as MockLLM,
            patch(
                "services.guardrails.InputGuardrail._call_judge",
                new_callable=AsyncMock,
                return_value="accept",
            ),
            patch("orchestration.react_loop.GoalJudge.evaluate", judge),
            patch(
                "orchestration.react_loop.TaskUnderstandingGenerator.generate",
                generate,
            ),
        ):
            llm = MockLLM.return_value
            llm.bind_tools.return_value = llm
            llm.ainvoke = AsyncMock(side_effect=responses)

            from orchestration.react_loop import build_graph

            graph = build_graph(
                agent_config=AgentConfig(
                    default_model="gpt-4o-mini",
                    models=[_fast_profile()],
                    goal_judge_enabled=True,
                ),
                tool_registry=registry,
                cache_dir=tmp_path / "cache",
                checkpointer=MemorySaver(),
                goal_judge_config_reader=reader,
                interrupt_before_execute_tool=True,
            )
            rt = LangGraphRuntime(graph=graph)

            # Leg 1: stream until the interrupt pauses the graph.
            first_leg = [
                ev
                async for ev in rt.run(
                    thread_id="thread-edit-rt",
                    input={"task_input": _TASK, "messages": []},
                    identity=identity,
                )
            ]
            trace_id = next(
                ev.trace_id for ev in first_leg
                if isinstance(ev, RunStartedDomain)
            )
            assert judge.await_count == 0, "paused run must not reach the judge"

            # Leg 2: the edit (what POST /run/understanding/{thread_id} does).
            _old, new = await rt.update_task_understanding(
                thread_id="thread-edit-rt",
                trace_id=trace_id,
                restated_intent="Only compare the options.",
                success_conditions=[
                    "The answer compares the available options.",
                    "The comparison is grounded in the task text.",
                ],
            )
            assert new["source"] == "user_edited"

            # Leg 3: resume through the stream path.
            resumed = [
                ev
                async for ev in rt.run(
                    thread_id="thread-edit-rt",
                    input={"_resume": True},
                    identity=identity,
                )
            ]

        resumed_start = next(
            ev for ev in resumed if isinstance(ev, RunStartedDomain)
        )
        assert resumed_start.trace_id == trace_id, "resume must keep the trace"
        cards = [ev for ev in resumed if isinstance(ev, TaskUnderstood)]
        assert cards and cards[-1].source == "user_edited"
        assert judge.await_count == 1
        assert _judge_conditions(judge) == new["success_conditions"]
        gj = _sink.goal_judge[0]["ai_input"]
        assert gj["conditions_source"] == "user_edited"
        assert gj["restated_intent"] == "Only compare the options."
