"""L1 property tests for AgentState reducers (T3 Step 5a).

The headline is the ``worker_results`` reducer canary: N concurrent branch
appends in a single superstep must merge with **none lost**. This is the P1
property that guards against the two ways the fan-out join could silently lose a
survivor (plan §2 Step 5a / §5 Risks):

  1. using ``_append_list`` (dedups by ``step_id``) instead of ``operator.add``
     would drop a same-id branch result, and
  2. LangGraph raises ``INVALID_CONCURRENT_GRAPH_UPDATE`` for a non-reducer key
     written by parallel branches.

Pure, deterministic, no graph, <10s, zero flake (A-style).
"""

from __future__ import annotations

import operator
from typing import get_args, get_type_hints

import pytest

from orchestration.state import AgentState


def _reducer_for(key: str):
    """Extract the reducer callable from an Annotated AgentState field."""
    hints = get_type_hints(AgentState, include_extras=True)
    annotated = hints[key]
    args = get_args(annotated)  # (base_type, *metadata)
    assert len(args) >= 2, f"{key} is not Annotated with a reducer"
    return args[1]


def test_worker_results_uses_additive_reducer() -> None:
    """worker_results must use operator.add, NOT a dedup reducer — a dedup
    reducer would silently drop a same-id branch result."""
    assert _reducer_for("worker_results") is operator.add


@pytest.mark.parametrize("n", [2, 3, 5, 8])
def test_worker_results_merge_loses_nothing(n: int) -> None:
    """THE CANARY (P1): N branches each appending one result merge to exactly N
    entries — none lost — even when the branch_ids collide on a default."""
    reducer = _reducer_for("worker_results")

    merged: list[dict] = []
    # Simulate N concurrent branch deltas, each a single-element list. Two of
    # them deliberately share step_id=0 (the trap a dedup reducer would spring).
    branch_deltas = [
        [{"branch_id": i, "step_id": 0, "status": "completed", "output": f"r{i}"}]
        for i in range(n)
    ]
    for delta in branch_deltas:
        merged = reducer(merged, delta)

    assert len(merged) == n, "a branch result was silently dropped"
    assert sorted(b["branch_id"] for b in merged) == list(range(n))


def test_worker_results_preserves_failure_sentinel() -> None:
    """A failed branch's sentinel survives alongside successful branches (the
    MAST-bounded guard — survivors are never erased by a failure)."""
    reducer = _reducer_for("worker_results")
    merged: list[dict] = []
    merged = reducer(merged, [{"branch_id": 1, "status": "completed", "output": "ok"}])
    merged = reducer(
        merged, [{"branch_id": 2, "status": "failed", "error": "boom", "output": ""}]
    )
    merged = reducer(merged, [{"branch_id": 3, "status": "completed", "output": "ok"}])

    assert len(merged) == 3
    statuses = {b["branch_id"]: b["status"] for b in merged}
    assert statuses == {1: "completed", 2: "failed", 3: "completed"}


# ════════════════════════════════════════════════════════════════════════════
# C1 Phase 3 — last_compaction_step canary (design §6 / §6.1).
#
# The cooldown marker stamped at the WRITE seam (evaluate_node) must:
#   1. be a PLAIN int (NOT Annotated[int, operator.add]) — the stamp is the
#      step_count at which a fold landed, NOT a running sum. operator.add
#      would silently double the value across checkpoint round-trips.
#   2. survive checkpoint reload last-write-wins (a fresh write overwrites
#      the previous value verbatim).
#   3. resolve to 0 when absent from a pre-C1 checkpoint (default/missing =
#      "never folded") so the first fold on a resumed legacy run is allowed.
# ════════════════════════════════════════════════════════════════════════════


def test_last_compaction_step_is_plain_int_not_annotated() -> None:
    """The cooldown stamp is overwrite-semantics — Annotated[int, operator.add]
    would silently double it across checkpoint round-trips and break §6.1.
    """
    hints = get_type_hints(AgentState, include_extras=True)
    assert "last_compaction_step" in hints, (
        "AgentState is missing the C1 last_compaction_step field"
    )
    annotated_args = get_args(hints["last_compaction_step"])
    # A plain int hint has zero metadata args; an Annotated alias has ≥2.
    assert annotated_args == (), (
        "last_compaction_step MUST be a plain int (last-write-wins), "
        f"not Annotated; got metadata: {annotated_args[1:] if annotated_args else None}"
    )


def test_last_compaction_step_round_trip_last_write_wins() -> None:
    """A StateGraph compiled with a MemorySaver checkpointer must reload the
    most recent write of last_compaction_step verbatim — the load-bearing
    invariant the cooldown gate at evaluate_node:2061 relies on.

    The node writes a CONSTANT (not a derived value) so this test pins the
    reducer for ``last_compaction_step`` alone — ``step_count`` separately
    uses operator.add and would sum across invokes if mixed into the stamp.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph

    # State a closure variable the node will stamp into the field; flip it
    # between invokes so we can prove the second value overwrites the first.
    next_stamp: list[int] = [5]

    def stamp(state: AgentState) -> dict:
        return {"last_compaction_step": next_stamp[0]}

    builder = StateGraph(AgentState)
    builder.add_node("stamp", stamp)
    builder.set_entry_point("stamp")
    builder.set_finish_point("stamp")
    graph = builder.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "c1-canary"}}

    # First write — stamp the fold at "step 5".
    first = graph.invoke({}, cfg)
    assert first["last_compaction_step"] == 5

    # Second write — stamp the fold at "step 11" on the same thread.
    # operator.add semantics would yield 5+11=16 here; last-write-wins gives 11.
    next_stamp[0] = 11
    second = graph.invoke({}, cfg)
    assert second["last_compaction_step"] == 11, (
        "last_compaction_step is summing across writes — wrong reducer"
    )


def test_last_compaction_step_absent_defaults_to_zero() -> None:
    """A pre-C1 checkpoint that never wrote the field must read as 0 (= never
    folded), and a node that gates on it must not raise KeyError. Reading the
    state via the same checkpointer simulates the legacy-resume path.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph

    seen: dict[str, int] = {}

    def read_only(state: AgentState) -> dict:
        # The gate Phase 5 will write: `state.get("last_compaction_step", 0)`.
        # That call must return 0 on a thread where the field was never written.
        seen["value"] = state.get("last_compaction_step", 0)
        return {}

    builder = StateGraph(AgentState)
    builder.add_node("probe", read_only)
    builder.set_entry_point("probe")
    builder.set_finish_point("probe")
    graph = builder.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "c1-legacy"}}
    # Invoke with a state shape that omits last_compaction_step entirely —
    # the legacy checkpoint shape.
    graph.invoke({"step_count": 0, "task_id": "legacy-task"}, cfg)

    assert seen.get("value") == 0, "absent last_compaction_step must read as 0"
