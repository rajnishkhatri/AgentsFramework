"""LangGraph AgentState TypedDict (extends MessagesState).

This is the only file in the orchestration layer that imports langgraph.
All other orchestration files import from this module for the state type.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from langgraph.graph import MessagesState


def _append_list(existing: list, new: list) -> list:
    """Append-only reducer. Deduplicates by step_id to prevent checkpoint reload duplication."""
    seen_ids = {item.get("step_id", id(item)) for item in existing}
    return existing + [
        item for item in new if item.get("step_id", id(item)) not in seen_ids
    ]


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

    tool_cache: dict[str, Any]

    workflow_id: str
    registered_agent_id: str
    agent_facts_verified: bool

    current_workflow_phase: str

    # Story 1.3: error propagation from call_llm_node to evaluate_node
    last_llm_error: str
    last_llm_error_code: int | None

    # Story 2.3: rollback tracking per model tier
    rollback_count: Annotated[int, operator.add]
    rollback_history: Annotated[list[dict], _append_list]
