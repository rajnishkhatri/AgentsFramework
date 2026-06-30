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


def _merge_dict(
    existing: dict[str, Any] | None, new: dict[str, Any] | None
) -> dict[str, Any]:
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

    # The user's per-run model pin (UI dropdown), seeded from the run input dict.
    # Distinct from ``selected_model`` (which the route node OVERWRITES each step
    # with the chosen profile name): the router reads ``pinned_model`` but never
    # writes it, so a pin set on the first step persists unchanged across every
    # step of the run (and, on resume, rides the checkpoint). Empty => "Auto".
    pinned_model: str
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
    # C1 Phase 3 (docs/plans/c1_message_compaction.design.md §6): the
    # step_count at which the last successful message-history fold landed.
    # PLAIN int (NOT Annotated[int, operator.add]) — the cooldown gate at the
    # WRITE seam reads this as "stamp of the last fold", overwrite-semantics.
    # An additive reducer would silently double the stamp across checkpoint
    # round-trips and break the cooldown invariant. Default/absent = 0 = never
    # folded, so a pre-C1 checkpoint resuming on this code permits the first
    # fold without a migration (§6.1 backward-compat).
    last_compaction_step: int

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
    # Phase 1 (T1 plan-and-execute): the chosen plan artifact (LLM-generated or
    # the deterministic floor), serialized via PlanArtifact.model_dump. Built
    # once per task at step 0 and memoized on plan_artifact_task_id — route_node
    # re-runs every iteration, so without this the LLM plan would be re-requested
    # (cost) or silently swapped for the deterministic floor on re-entry
    # (fingerprint churn). The replan gate reuses this stored plan and rebuilds
    # only when a tool result invalidates it (plan_is_stale). Same memoize-on-
    # task_id discipline as task_understanding_task_id.
    plan_artifact: dict[str, Any]
    plan_artifact_task_id: str
    # Phase 1 (T1): how many times the plan was rebuilt mid-task because a tool
    # result invalidated it (plan_is_stale). operator.add like rollback_count;
    # surfaced on STEP_PLANNED so the trace shows replan activity.
    replan_count: Annotated[int, operator.add]
    # Phase 2 (T2 reflexion): append-only verbal critiques — the "semantic
    # gradient" (Reflexion, arxiv 2303.11366). reflect_node appends one entry
    # per re-entry: {step_id, attempt, critique, unmet_conditions, task_id}.
    # Append-only is what lets prior critiques survive a checkpoint reload and
    # accumulate; call_llm_node folds them into the system prompt on re-entry,
    # and len(reflections) is the attempt counter decide_reentry checks against
    # the budget ceiling (no separate counter to drift).
    #
    # task_id GUARD (ADR-0005): the channel is keyed on the LangGraph thread_id,
    # which a chat client REUSES across turns, while task_id is minted fresh per
    # turn — so a prior turn's critique physically persists into the next turn's
    # state. The reducer is append-only, so the last-write-wins reset used by
    # planning_depth_task_id / task_understanding_task_id can't apply here;
    # instead each entry carries the task_id it was recorded under (reflect_node
    # stamps `task_id or workflow_id`, never empty), and EVERY consumer reads
    # through the orchestration helper react_loop._task_reflections (which wraps
    # components.reflexion.reflections_for_task) to scope to the current task.
    # A different non-empty task_id is excluded (the leak); an untagged legacy
    # entry is kept as the current task's (a one-deploy grace). Without this a
    # prior question's failure critique bleeds into the next question's prompt
    # AND pre-consumes the reflexion budget.
    reflections: Annotated[list[dict[str, Any]], _append_list]
    # Phase 4 (T3 fan-out): per-branch worker results merged across the parallel
    # superstep — one entry per Send branch: {branch_id, status, output, error}.
    # MUST use operator.add, NOT _append_list: concurrent branch writes in a
    # single superstep need the additive reducer or LangGraph raises
    # INVALID_CONCURRENT_GRAPH_UPDATE; and _append_list dedups by step_id, which
    # would SILENTLY DROP a same-id branch result (e.g. two branches that both
    # default to step_id 0). join_node reads the merged list and synthesizes one
    # answer; a worker that fails appends a sentinel so survivors are never
    # erased (the MAST-bounded guard, plan §3.5a).
    worker_results: Annotated[list[dict[str, Any]], operator.add]
    # Phase 4 (T3): transient supervisor decision handed from supervisor_node to
    # the _route_fanout conditional edge ({decision, decision_id, branches,
    # reason}). Plain last-write-wins key — it is read within the same superstep
    # and not accumulated. Lives on state (not a closure) so the routing fn,
    # which only receives state, can read it.
    fanout_decision: dict[str, Any]
    # Phase 2: the evaluate->reflect routing carriers. evaluate_node computes the
    # verdict/outcome inside its terminal block but the routing fn runs after, so
    # these scalars are persisted into the delta for _should_continue_or_escalate
    # to read (it cannot re-run the judge). Last-write-wins (plain keys): only the
    # most recent verdict matters for the next routing decision.
    last_task_outcome: str
    last_unmet_conditions: list[str]
    last_final_answer: str

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

    # Phase 1 memory wiring (docs/plans/memory_layer_wiring.plan.md). The subject
    # the long-term memory is namespaced to — LangGraphRuntime threads
    # identity.owner here at run start (it already derives eval_user_id from it).
    # A memory store/recall never uses a user_id other than this (cross-user-leak
    # guard). Plain last-write-wins.
    user_id: str
    # The recalled-memory block (already rendered to a system-prompt string by
    # components.memory_context.render_recall_block) that call_llm/supervisor
    # append to additional_instructions. Empty string = no memory / recall
    # degraded / flag off → the prompt stays byte-identical. Last-write-wins.
    recalled_memories: str
    # The task_id recall was performed for. route_node recalls at most once per
    # run and memoizes on this — reflexion reflect→route re-entry keeps the same
    # task_id, so the memoize check (should_recall's `memoized` arm) reuses the
    # stored block instead of re-querying the backend every lap. Same memoize-on-
    # task_id discipline as planning_depth_task_id/task_understanding_task_id;
    # a new task_id on the thread regenerates.
    recalled_memories_task_id: str
    # How many memories the recall returned this run (metadata only — NEVER
    # content, preserving the privacy invariant). Surfaced to the UI's
    # transparent-recall indicator via a MemoryRecalled domain event emitted
    # from the route node's output. Memoized alongside recalled_memories on
    # recalled_memories_task_id, so a reflexion lap reports the same count
    # without re-querying. 0 = no recall / degraded / flag off. Last-write-wins.
    recalled_memories_count: int
    # Phase B (recalled-memories-per-chat): the stable keys of the records
    # actually injected this turn — identifiers, NEVER payload content (the
    # privacy invariant holds; the owner joins them against their own memory
    # panel to render the per-chat eval/reject view). Memoized alongside
    # recalled_memories_count; [] = no recall / degraded / flag off.
    recalled_memories_keys: list[str]
