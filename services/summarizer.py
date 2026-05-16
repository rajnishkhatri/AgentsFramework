"""Deterministic trajectory compaction helpers."""

from __future__ import annotations

from pydantic import BaseModel


class CompactionResult(BaseModel):
    should_compact: bool
    summary_text: str
    offload_ref: str


def should_compact_trajectory(*, current_token_count: int, token_threshold: int) -> bool:
    """Return True when token pressure crosses configured threshold."""
    return current_token_count >= max(1, token_threshold)


def build_compaction_summary(
    *,
    task_input: str,
    reasoning_trace: list[str],
    tool_results: list[dict],
    latest_output: str,
) -> str:
    """Build a compact deterministic summary preserving critical context."""
    recent_trace = reasoning_trace[-3:] if reasoning_trace else []
    recent_tools = [str(item.get("tool_name", "")) for item in tool_results[-3:]]
    tools_line = ", ".join([name for name in recent_tools if name]) or "none"
    trace_line = " | ".join([entry[:120] for entry in recent_trace]) or "none"
    latest_line = (latest_output or "").strip()[:280] or "(empty)"
    task_line = (task_input or "").strip()[:200]
    return (
        "Trajectory compaction summary:\n"
        f"- task: {task_line}\n"
        f"- recent_tools: {tools_line}\n"
        f"- recent_reflection: {trace_line}\n"
        f"- latest_output: {latest_line}\n"
    )
