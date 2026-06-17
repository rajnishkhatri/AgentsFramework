"""L1 pure-TDD tests for components/memory_context.py (Protocol A).

Phase 1 memory wiring (docs/plans/memory_layer_wiring.plan.md). These are the
OBP-1 formatting helpers and the OBP-2 recall predicate — the only place
recall/store *logic* lives, so route_node can stay a thin OBP-3 wrapper.

Failure paths first (TAP-4): the predicate's reject rows and the formatters'
empty/degenerate inputs are asserted before the happy path. No LangGraph, no
LLM, no AgentState — zero-flake by construction.
"""

from __future__ import annotations

from components.memory_context import (
    build_store_payload,
    memory_subject,
    render_recall_block,
    should_recall,
)
from services.long_term_memory import MemoryRecord


def _rec(text: str, *, key: str = "k", metadata: dict | None = None) -> MemoryRecord:
    return MemoryRecord(
        user_id="u1",
        key=key,
        payload={"text": text},
        metadata=metadata or {},
    )


# ── OBP-2 predicate: should_recall (reject rows first) ────────────────────


def test_should_recall_false_when_disabled() -> None:
    """Flag OFF → never recall, regardless of user_id/memoization."""
    assert should_recall(enabled=False, user_id="u1", memoized=False) is False


def test_should_recall_false_without_user_id() -> None:
    """No subject → no recall (cross-user-leak guard; nothing to namespace)."""
    assert should_recall(enabled=True, user_id="", memoized=False) is False


def test_should_recall_false_when_already_memoized() -> None:
    """Memoized this task → reuse state, do not re-query the backend.

    This is the load-bearing T2 property: a reflect→route reflexion lap keeps
    the same task_id, so the second pass sees memoized=True and skips search.
    """
    assert should_recall(enabled=True, user_id="u1", memoized=True) is False


def test_should_recall_true_only_when_enabled_user_and_fresh() -> None:
    assert should_recall(enabled=True, user_id="u1", memoized=False) is True


# ── OBP-1 formatter: render_recall_block (empty/degenerate first) ─────────


def test_render_recall_block_empty_is_empty_string() -> None:
    """Zero records → empty string (byte-identical prompt = the no-op shape)."""
    assert render_recall_block([]) == ""


def test_render_recall_block_none_is_empty_string() -> None:
    """Degraded recall passes None → empty string, never a crash."""
    assert render_recall_block(None) == ""  # type: ignore[arg-type]


def test_render_recall_block_includes_record_text() -> None:
    block = render_recall_block([_rec("prefers metric units")])
    assert "prefers metric units" in block


def test_render_recall_block_has_a_stable_header() -> None:
    """The block is a labelled section appended to additional_instructions."""
    block = render_recall_block([_rec("a fact")])
    # A reader (and the system prompt) must see WHY this text is here.
    assert block.lower().startswith("relevant")
    assert "remember" in block.lower()


def test_render_recall_block_lists_each_record() -> None:
    block = render_recall_block([_rec("fact one"), _rec("fact two", key="k2")])
    assert "fact one" in block
    assert "fact two" in block


def test_render_recall_block_is_deterministic() -> None:
    recs = [_rec("alpha"), _rec("beta", key="k2")]
    assert render_recall_block(recs) == render_recall_block(recs)


def test_render_recall_block_tolerates_missing_text_key() -> None:
    """A record whose payload lacks the conventional text key must not crash."""
    rec = MemoryRecord(user_id="u1", key="k", payload={"other": "v"}, metadata={})
    block = render_recall_block([rec])
    assert isinstance(block, str)  # renders *something*, never raises


# ── OBP-1 builder: build_store_payload ────────────────────────────────────


def test_build_store_payload_carries_task_and_answer() -> None:
    payload = build_store_payload("what units?", "you prefer metric")
    assert payload["task_input"] == "what units?"
    assert payload["answer"] == "you prefer metric"


def test_build_store_payload_is_a_plain_dict() -> None:
    """Store payload must be a JSON-serializable plain dict (MemoryRecord.payload)."""
    payload = build_store_payload("t", "a")
    assert type(payload) is dict
    assert all(isinstance(k, str) for k in payload)


def test_build_store_payload_handles_empty_answer() -> None:
    payload = build_store_payload("t", "")
    assert payload["answer"] == ""
    assert payload["task_input"] == "t"


# ── cross-user-leak guard: memory_subject ─────────────────────────────────


def test_memory_subject_blank_is_no_subject() -> None:
    assert memory_subject("") == ""
    assert memory_subject("   ") == ""


def test_memory_subject_anonymous_is_no_subject() -> None:
    """The 'anonymous' sentinel must never be a memory subject (leak guard)."""
    assert memory_subject("anonymous") == ""


def test_memory_subject_real_user_passes_through_trimmed() -> None:
    assert memory_subject("  alice ") == "alice"
    assert memory_subject("u-123") == "u-123"
