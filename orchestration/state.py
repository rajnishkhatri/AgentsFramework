"""LangGraph AgentState TypedDict (extends MessagesState).

This is the only file in the orchestration layer that imports langgraph.
All other orchestration files import from this module for the state type.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

from langgraph.graph import MessagesState


def _append_list(existing: list, new: list) -> list:
    """Append-only reducer. Deduplicates by step_id to prevent checkpoint reload duplication."""
    seen_ids = {item.get("step_id", id(item)) for item in existing}
    return existing + [
        item for item in new if item.get("step_id", id(item)) not in seen_ids
    ]


def _append_list_by_record_id(existing: list, new: list) -> list:
    """Append-only reducer deduplicating by ``record_id`` for tool results."""
    seen_ids = {item.get("record_id", id(item)) for item in existing}
    return existing + [
        item for item in new if item.get("record_id", id(item)) not in seen_ids
    ]


def _merge_dict(existing: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    """Merge dictionaries with new values overriding existing values."""
    if not existing:
        return dict(new or {})
    if not new:
        return dict(existing)
    merged = dict(existing)
    merged.update(new)
    return merged


class TodoItem(TypedDict):
    id: str
    content: str
    status: Literal["pending", "in_progress", "completed", "cancelled"]


class AgentState(MessagesState):
    task_id: str
    task_input: str

    selected_model: str
    routing_reason: str
    model_history: Annotated[list[dict], _append_list]

    step_count: Annotated[int, operator.add]
    total_cost_usd: Annotated[float, operator.add]
    total_input_tokens: Annotated[int, operator.add]
    total_output_tokens: Annotated[int, operator.add]

    consecutive_errors: int
    last_error_type: str
    error_history: Annotated[list[dict], _append_list]
    retry_count_current_step: int
    backoff_until: float | None

    current_token_count: int
    truncation_applied: bool

    last_outcome: str
    reasoning_trace: Annotated[list[str], operator.add]

    step_results: Annotated[list[dict], _append_list]
    tool_results: Annotated[list[dict], _append_list_by_record_id]

    tool_cache: dict[str, Any]
    files: Annotated[dict[str, str], _merge_dict]
    todos: list[TodoItem]
    plan_ref: str
    # Phase 4 (E10): SHA-256 of the last emitted plan's identity. route_node
    # re-runs every iteration; comparing the new fingerprint against this lets
    # it stamp ``plan_changed`` on each STEP_PLANNED so the relay can suppress
    # the duplicate EXPORT (the JSONL row is recorded every iteration).
    last_plan_fingerprint: str
    # task_understanding plan §4.5: plan-time TaskUnderstanding artifact
    # (restated_intent + success_conditions + provenance), written once at
    # step 0 in route_node and memoized — route_node re-runs every loop
    # iteration but generation must fire at most once per run.
    task_understanding: dict[str, Any]
    # The task_id the artifact above was derived for. Thread state outlives
    # the turn (checkpointer) while task_id is minted per run, so route_node
    # regenerates when these diverge — a later turn must never be judged
    # against an earlier turn's conditions (governance audit 3921c61b).
    # Kept OUTSIDE the artifact dict: its shape is wire-synced to the
    # frontend kernel, and the edit endpoint replaces the whole dict — a
    # sibling key survives user edits.
    task_understanding_task_id: str
    # F10 Tier-2: one cheap-tier "why/how" recap written by reasoning_recap
    # at run end; surfaced to the UI as Custom{name="reasoning_summary"}.
    reasoning_summary: str
    planning_depth: Literal["L0", "L1", "L2"]
    planning_depth_reason: str
    # The task_id the planning_depth above was selected for. route_node
    # recomputes depth every loop iteration, and select_planning_depth
    # collapses to L0 once this task has produced a tool result
    # (post-tool-synthesis). Memoizing the step-0 depth per task — same
    # discipline as task_understanding_task_id — keeps the intended depth
    # stable for the whole task instead of flipping to L0 after the first
    # tool call. Thread state outlives the turn; a new task_id regenerates.
    planning_depth_task_id: str

    workflow_id: str
    registered_agent_id: str
    agent_facts_verified: bool
    agent_capabilities: list[str]

    current_workflow_phase: str

    # No-progress graceful wrap-up: tracks whether the synthesis directive was injected
    no_progress_directive_sent: bool

    # Story 1.3: error propagation from call_llm_node to evaluate_node
    last_llm_error: str
    last_llm_error_code: int | None

    # Story 2.3: rollback tracking per model tier
    rollback_count: Annotated[int, operator.add]
    rollback_history: Annotated[list[dict], _append_list]
