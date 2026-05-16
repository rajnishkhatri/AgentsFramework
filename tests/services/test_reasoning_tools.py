"""L2 contract tests for think tool and trajectory summarizer."""

from __future__ import annotations

from services.summarizer import build_compaction_summary, should_compact_trajectory
from services.tools.think_tool import execute_think_tool


def test_execute_think_tool_emits_reasoning_trace_delta() -> None:
    result = execute_think_tool({
        "thought": "Need to check migration risk before final answer.",
        "category": "risk",
        "next_action": "Inspect constraints",
    })
    assert result.ok is True
    assert result.state_delta is not None
    assert "reasoning_trace" in result.state_delta
    assert len(result.state_delta["reasoning_trace"]) == 1


def test_should_compact_trajectory_threshold() -> None:
    assert should_compact_trajectory(current_token_count=4000, token_threshold=3000) is True
    assert should_compact_trajectory(current_token_count=1500, token_threshold=3000) is False


def test_build_compaction_summary_includes_critical_sections() -> None:
    summary = build_compaction_summary(
        task_input="Compare architectures and propose migration roadmap.",
        reasoning_trace=["risk check", "decision rationale"],
        tool_results=[{"tool_name": "web_search"}],
        latest_output="Draft answer",
    )
    assert "recent_tools:" in summary
    assert "recent_reflection:" in summary
