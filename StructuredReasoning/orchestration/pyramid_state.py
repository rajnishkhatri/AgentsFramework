"""LangGraph state for the Pyramid ReACT agent.

Like ``orchestration/state.py``, this is the only file in the inner
orchestration layer that imports ``langgraph``. All other inner
orchestration files import the state from this module.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any

from langgraph.graph import MessagesState


def _append_dicts(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append-only reducer for log lists. No deduplication: each entry is
    a distinct event recorded at a specific point in time."""
    return existing + list(new)


class PyramidState(MessagesState):
    """State carried through the four-phase pyramid graph.

    PR 1 walking-skeleton fields only: ``analysis_output_json`` holds the
    final structured output as a JSON-mode dict so LangGraph's checkpoint
    serializer can persist it. PR 2 will add ``issue_tree``,
    ``hypotheses``, ``evidence``, etc., as separate state slots tied to
    individual phase nodes.
    """

    workflow_id: str
    task_id: str
    task_input: str

    # PR 1: single-call output. PR 2 will replace this with per-phase fields.
    analysis_output_json: dict[str, Any]
    parse_error: str

    # Iteration accounting (PR 3 will drive ``should_iterate`` from these).
    iteration_count: Annotated[int, operator.add]
    max_iterations: int

    # Cost / token bookkeeping (mirrors outer AgentState slots).
    total_cost_usd: Annotated[float, operator.add]
    total_input_tokens: Annotated[int, operator.add]
    total_output_tokens: Annotated[int, operator.add]

    # Outcome surface for the CLI / persistence layer.
    last_outcome: str
    reasoning_trace: Annotated[list[str], operator.add]

    # Per-phase decision log (filled in PR 2; declared now so PR 1 tests
    # round-trip the same shape).
    phase_log: Annotated[list[dict], _append_dicts]
