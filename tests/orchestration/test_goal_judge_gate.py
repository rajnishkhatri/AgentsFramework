"""L4 Behavioral: Fix 2 (Option B) goal-judge downgrade gate in react_loop.

The gate is a thin (AP-5) success->partial wrapper around the L3
``GoalJudge`` verdict. It reads ONLY ``goal_met`` and is guarded by the
``goal_judge_downgrade_enabled`` flag so it ships dark (shadow mode).

Test strategy (Protocol D — simulation / failure-mode matrix):
  - Mock the LLM (no live calls) and patch ``GoalJudge.evaluate`` so the
    verdict is the single controlled input dimension.
  - FAILURE PATHS FIRST (TAP-4): goal_met=True must NOT downgrade; the flag
    OFF must keep the outcome (shadow); a non-success source must never be
    touched (no illegal transition / no upgrade). The acceptance downgrade is
    asserted last.
  - We read the outcome back from the BlackBox TASK_COMPLETED event — the
    observable behaviour — never the gate's internals.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from components.schemas import GoalVerdict
from services.base_config import AgentConfig, ModelProfile
from services.goal_judge_runtime_config import InMemoryGoalJudgeConfigReader


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _completion_details(tmp_path, workflow_id: str) -> dict:
    """Return the single TASK_COMPLETED event's details for a workflow."""
    trace_file = (
        tmp_path / "cache" / "black_box_recordings" / workflow_id / "trace.jsonl"
    )
    events = [
        json.loads(ln) for ln in trace_file.read_text().splitlines() if ln
    ]
    completed = [e for e in events if e.get("event_type") == "task_completed"]
    assert len(completed) == 1, "Expected exactly one TASK_COMPLETED event"
    return completed[0]["details"]


async def _run_with_verdict(
    tmp_path,
    *,
    workflow_id: str,
    verdict: GoalVerdict,
    downgrade_enabled: bool,
    final_answer: str = "FINAL ANSWER: Paris is the capital of France.",
    max_cost_usd: float = 1.0,
    initial_cost: float = 0.0,
    seed_no_progress: bool = False,
    goal_judge_config_reader: InMemoryGoalJudgeConfigReader | None = None,
    goal_judge_enabled: bool = True,
) -> dict:
    """Drive the graph to completion with a controlled goal-judge verdict."""
    mock_response = MagicMock()
    mock_response.content = final_answer
    mock_response.tool_calls = []
    mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
    mock_response.response_metadata = {"model_name": "gpt-4o-mini"}

    agent_config = AgentConfig(
        default_model="gpt-4o-mini",
        models=[_fast_profile()],
        max_cost_usd=max_cost_usd,
        goal_judge_enabled=goal_judge_enabled,
        goal_judge_downgrade_enabled=downgrade_enabled,
    )

    graph_kwargs: dict = {
        "agent_config": agent_config,
        "cache_dir": tmp_path / "cache",
    }
    if goal_judge_config_reader is not None:
        graph_kwargs["goal_judge_config_reader"] = goal_judge_config_reader

    with (
        patch("langchain_litellm.ChatLiteLLM") as MockLLM,
        patch(
            "services.guardrails.InputGuardrail._call_judge",
            new_callable=AsyncMock,
            return_value="accept",
        ),
        patch(
            "orchestration.react_loop.GoalJudge.evaluate",
            new_callable=AsyncMock,
            return_value=verdict,
        ),
    ):
        MockLLM.return_value.ainvoke = AsyncMock(return_value=mock_response)

        from orchestration.react_loop import build_graph

        graph = build_graph(**graph_kwargs)
        initial_state: dict = {
            "task_id": "t",
            "task_input": "What is the capital of France?",
            "messages": [],
            "workflow_id": workflow_id,
            "total_cost_usd": initial_cost,
        }
        if seed_no_progress:
            initial_state["no_progress_directive_sent"] = True
        await graph.ainvoke(
            initial_state,
            config={"configurable": {"task_id": "t", "user_id": "u"}},
        )

    return _completion_details(tmp_path, workflow_id)


# ─────────────────────────────────────────────────────────────────────
# Failure paths first (TAP-4)
# ─────────────────────────────────────────────────────────────────────


class TestNoSpuriousDowngrade:
    @pytest.mark.asyncio
    async def test_goal_met_true_does_not_downgrade(self, tmp_path):
        """goal_met=True must NEVER downgrade, even with the flag ON."""
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-gm-true",
            verdict=GoalVerdict(goal_met=True, criteria_met=1.0),
            downgrade_enabled=True,
        )
        assert details["outcome"] == "success"
        assert details["downgrade_reason"] is None
        # goal_met=True → the gate would never fire.
        assert details["would_downgrade"] is False

    @pytest.mark.asyncio
    async def test_flag_off_is_shadow_only(self, tmp_path):
        """goal_met=False with the flag OFF must keep outcome=success."""
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-shadow",
            verdict=GoalVerdict(goal_met=False, criteria_met=0.0),
            downgrade_enabled=False,
        )
        assert details["outcome"] == "success"
        assert details["downgrade_reason"] is None
        assert details["goal_met"] is False  # overlay still records the verdict
        # Phase 1 (E1): the shadow signal is surfaced on TASK_COMPLETED so a
        # reader sees the gate *would* have fired without opening eval.goal_judge.
        assert details["would_downgrade"] is True

    @pytest.mark.asyncio
    async def test_no_progress_source_is_never_downgraded(self, tmp_path):
        """no_progress -> partial with goal_met=False must not fire the gate."""
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-no-progress",
            verdict=GoalVerdict(goal_met=False, criteria_met=0.0),
            downgrade_enabled=True,
            seed_no_progress=True,
        )
        assert details["outcome"] == "partial"
        assert details["downgrade_reason"] is None
        assert details["goal_met"] is False

    @pytest.mark.asyncio
    async def test_budget_terminal_site_bypasses_gate(self, tmp_path):
        """budget_exceeded is produced before the goal-judge gate is reached."""
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-budget",
            verdict=GoalVerdict(goal_met=False, criteria_met=0.0),
            downgrade_enabled=True,
            max_cost_usd=0.001,
            initial_cost=999.0,
        )
        assert details["outcome"] == "budget_exceeded"
        assert details.get("downgrade_reason") is None


# ─────────────────────────────────────────────────────────────────────
# Acceptance path
# ─────────────────────────────────────────────────────────────────────


class TestDowngradeApplied:
    @pytest.mark.asyncio
    async def test_goal_met_false_with_flag_on_downgrades(self, tmp_path):
        """goal_met=False + flag ON downgrades a clean success to partial."""
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-downgrade",
            verdict=GoalVerdict(goal_met=False, criteria_met=0.0),
            downgrade_enabled=True,
        )
        assert details["outcome"] == "partial"
        assert details["downgrade_reason"] == "goal_judge"

    @pytest.mark.asyncio
    async def test_graceful_failure_only_success_to_partial(self, tmp_path):
        """A graceful-failure verdict downgrades success->partial and no
        further — it is not double-penalised to failed."""
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-graceful",
            verdict=GoalVerdict(
                goal_met=False, criteria_met=0.0, graceful_failure=True
            ),
            downgrade_enabled=True,
        )
        assert details["outcome"] == "partial"
        assert details["downgrade_reason"] == "goal_judge"


class TestRuntimeConfigReaderInjection:
    @pytest.mark.asyncio
    async def test_injected_reader_overrides_agent_config_downgrade(self, tmp_path):
        """Per-run reader wins over static AgentConfig when injected."""
        reader = InMemoryGoalJudgeConfigReader(
            goal_judge_enabled=True,
            goal_judge_downgrade_enabled=True,
            source="test-injected",
        )
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-reader-on",
            verdict=GoalVerdict(goal_met=False, criteria_met=0.0),
            downgrade_enabled=False,
            goal_judge_config_reader=reader,
        )
        assert details["outcome"] == "partial"
        assert details["downgrade_reason"] == "goal_judge"

    @pytest.mark.asyncio
    async def test_malformed_runtime_config_stays_dark(self, tmp_path):
        """Malformed on-disk config with URI set → fail-dark (judge skipped)."""
        bad_file = tmp_path / "bad_goal_judge.json"
        bad_file.write_text('{"goal_judge_enabled": true, "typo_key": 1}', encoding="utf-8")
        from services.goal_judge_runtime_config import GoalJudgeRuntimeConfigReader

        reader = GoalJudgeRuntimeConfigReader(
            uri=f"file://{bad_file}",
            defaults_enabled=False,
            defaults_downgrade=False,
        )
        details = await _run_with_verdict(
            tmp_path,
            workflow_id="wf-malformed-dark",
            verdict=GoalVerdict(goal_met=False, criteria_met=0.0),
            downgrade_enabled=True,
            goal_judge_config_reader=reader,
            goal_judge_enabled=True,
        )
        assert details["outcome"] == "success"
        assert details["downgrade_reason"] is None
