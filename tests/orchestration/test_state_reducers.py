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
