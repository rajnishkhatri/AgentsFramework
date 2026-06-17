"""Memory recall/store helpers (framework-agnostic).

Phase 1 memory wiring (docs/plans/memory_layer_wiring.plan.md). This module
holds the **only** recall/store *logic*: the OBP-1 formatters that turn
backend records into a system-prompt block and a task into a store payload,
and the OBP-2 predicate that decides whether recall should run. Keeping it
here is what lets ``route_node`` stay a thin OBP-3 wrapper (it calls these the
same way it calls ``select_model`` / ``select_planning_depth`` — adapt state,
no logic).

Layer rules (I-1/I-3/I-5, enforced by tests/architecture/): no ``langgraph`` /
``langchain`` / ``orchestration`` / ``AgentState`` imports — only the
``services`` memory types. Pure functions, deterministic, zero-flake.

Privacy: these helpers never log; callers carry the privacy invariant (only
``user_id`` + ``key`` ever reach a log line, never payload content).
"""

from __future__ import annotations

from typing import Any

from services.long_term_memory import MemoryRecord

# Conventional payload field the deterministic v1 store writes the salient text
# under (see ``build_store_payload``). ``render_recall_block`` reads it back but
# tolerates its absence so a record written by another producer never crashes
# recall.
_TEXT_KEY = "text"

_RECALL_HEADER = "Relevant context you remember about this user:"

# The runtime uses "anonymous" as the sentinel subject when no real user is
# attached to a run (config["configurable"]["user_id"] default). Memory must
# never recall or store under it — doing so would pool every anonymous run into
# one shared cross-user bucket (the cross-user-leak guard). Treat it as no
# subject so should_recall/the store guard short-circuit.
_ANONYMOUS_SUBJECT = "anonymous"


def memory_subject(user_id: str) -> str:
    """Normalize a run's user_id to a memory subject, or '' for no subject.

    Pure helper (the cross-user-leak guard, OBP-1): the sentinel ``anonymous``
    and any falsy/blank value resolve to '' so the recall predicate and the
    store guard treat the run as having no subject to namespace by.
    """
    subject = (user_id or "").strip()
    if not subject or subject == _ANONYMOUS_SUBJECT:
        return ""
    return subject


def should_recall(*, enabled: bool, user_id: str, memoized: bool) -> bool:
    """OBP-2 predicate: should ``route_node`` query the backend this pass?

    Pure decision over scalars — takes no ``AgentState``. Recall fires only
    when memory is enabled, a subject is present to namespace by, and this
    task has not already recalled (the memoize-once guard). The ``memoized``
    arm is the load-bearing T2 property: a reflexion ``reflect → route`` lap
    keeps the same ``task_id``, so the second pass sees ``memoized=True`` and
    reuses the stored block instead of re-querying — one search per run.
    """
    return bool(enabled) and bool(user_id) and not memoized


def render_recall_block(records: list[MemoryRecord] | None) -> str:
    """OBP-1 formatter: top-k records → an ``additional_instructions`` block.

    Returns the empty string for no/zero records so the caller appends nothing
    and the system prompt stays byte-identical (the no-op / degraded shape).
    Each record contributes one bullet; a record missing the conventional text
    key falls back to a compact ``repr`` of its payload rather than raising —
    recall must never fail a run.
    """
    if not records:
        return ""
    lines = [_RECALL_HEADER]
    for record in records:
        payload: dict[str, Any] = getattr(record, "payload", None) or {}
        text = payload.get(_TEXT_KEY)
        if not isinstance(text, str) or not text:
            # Defensive: a record written by another producer (or a future
            # typed store) may not use _TEXT_KEY. Surface *something* readable
            # without leaking structure into a crash.
            text = repr(payload)
        lines.append(f"- {text}")
    return "\n".join(lines)


def build_store_payload(task_input: str, answer: str) -> dict[str, Any]:
    """OBP-1 builder: the deterministic v1 store payload.

    v1 is a deterministic distillation — the task and the final answer, no LLM
    call (the typed extractor is Phase 2). A plain JSON-serializable dict so it
    drops straight into ``MemoryRecord.payload``; the salient text lives under
    ``_TEXT_KEY`` so ``render_recall_block`` can read it back on a later run.
    """
    return {
        "task_input": task_input,
        "answer": answer,
        _TEXT_KEY: f"Task: {task_input}\nAnswer: {answer}",
    }


__all__ = [
    "should_recall",
    "render_recall_block",
    "build_store_payload",
    "memory_subject",
]
