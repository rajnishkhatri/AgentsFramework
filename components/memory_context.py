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

# Metadata keys read off a record at render time. ``score`` is the backend's
# relevance/similarity score for the query (Mem0 attaches one; the in-memory
# substring backend does not) — the A2 relevance floor only applies when it is
# present, so a backend that omits it is unaffected. ``salience`` is the
# extractor's confidence the typed-autocapture store wrote (A3) — absent on the
# v1 deterministic store, which renders unmarked.
_SCORE_KEY = "score"
_SALIENCE_KEY = "salience"

_RECALL_HEADER = "Relevant context you remember about this user:"

# A3 provenance tier prefixes (memory-os ground-truth hierarchy): a record at or
# above ``authoritative_at`` salience is marked authoritative, below it
# speculative. A record carrying no salience renders with NO prefix (the v1
# deterministic store writes none — backward-compatible with today's bullet).
_TIER_AUTHORITATIVE = "[confirmed]"
_TIER_SPECULATIVE = "[inferred]"

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


def _record_text(record: MemoryRecord) -> str:
    """The renderable text for one record (the conventional ``text`` key).

    A record written by another producer (or a future typed store) may not use
    ``_TEXT_KEY``; surface a compact ``repr`` of the payload rather than raising
    — recall must never fail a run.
    """
    payload: dict[str, Any] = getattr(record, "payload", None) or {}
    text = payload.get(_TEXT_KEY)
    if not isinstance(text, str) or not text:
        return repr(payload)
    return text


def _normalize(text: str) -> str:
    """Dedup key (A2): case-insensitive, whitespace-collapsed."""
    return " ".join(text.lower().split())


def _below_floor(record: MemoryRecord, min_relevance: float) -> bool:
    """A2 relevance floor: drop a record only when it carries a score BELOW the
    floor. A record with no ``score`` metadata (the in-memory backend) is never
    dropped — the floor only bites against a backend that scores its matches.
    """
    if min_relevance <= 0.0:
        return False
    metadata: dict[str, Any] = getattr(record, "metadata", None) or {}
    score = metadata.get(_SCORE_KEY)
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        return False
    return float(score) < min_relevance


def _tier_prefix(record: MemoryRecord, authoritative_at: float) -> str:
    """A3 provenance prefix: ``[confirmed]``/``[inferred]`` from salience, or
    '' when the record carries no salience (backward-compatible unmarked bullet).
    """
    metadata: dict[str, Any] = getattr(record, "metadata", None) or {}
    salience = metadata.get(_SALIENCE_KEY)
    if not isinstance(salience, (int, float)) or isinstance(salience, bool):
        return ""
    tier = _TIER_AUTHORITATIVE if float(salience) >= authoritative_at else _TIER_SPECULATIVE
    return f"{tier} "


def filter_recall_records(
    records: list[MemoryRecord] | None,
    *,
    min_relevance: float = 0.0,
) -> list[MemoryRecord]:
    """A2: the records that survive the relevance floor + exact-text dedup.

    Pure and order-preserving. The node calls this to count what was actually
    injected (the carrier/indicator count must reflect the survivors, not the
    raw top-k); ``render_recall_block`` renders the same survivors. Defaults
    reproduce the original "keep everything" behavior: a record with no
    ``score`` is never dropped and ``min_relevance=0.0`` applies no floor, so
    only exact-duplicate text is ever removed.
    """
    if not records:
        return []
    kept: list[MemoryRecord] = []
    seen: set[str] = set()
    for record in records:
        if _below_floor(record, min_relevance):
            continue
        key = _normalize(_record_text(record))
        if key in seen:
            continue
        seen.add(key)
        kept.append(record)
    return kept


def render_recall_block(
    records: list[MemoryRecord] | None,
    *,
    min_relevance: float = 0.0,
    authoritative_at: float = 0.8,
) -> str:
    """OBP-1 formatter: top-k records → an ``additional_instructions`` block.

    Returns the empty string for no/zero records — and for the case where every
    record is filtered out — so the caller appends nothing and the system prompt
    stays byte-identical (the no-op / degraded shape).

    Two optional, backward-compatible refinements over the raw top-k (defaults
    reproduce the original behavior exactly):

    - **A2 relevance floor + dedup** (``min_relevance``, memory-os surgical
      injection): drop records whose backend ``score`` is below the floor, and
      collapse exact-duplicate text to one bullet. ``min_relevance=0.0`` (default)
      applies no floor; a backend that attaches no score is unaffected. Dedup is
      always on (exact-text only — cheap, no embedding on the hot path).
    - **A3 salience tiers** (``authoritative_at``, memory-os ground-truth
      hierarchy): prefix each bullet with ``[confirmed]``/``[inferred]`` from the
      record's ``salience`` metadata. A record with no salience renders unmarked
      (the v1 deterministic store writes none — exactly today's bullet).
    """
    kept = filter_recall_records(records, min_relevance=min_relevance)
    if not kept:
        return ""
    lines = [_RECALL_HEADER]
    for record in kept:
        text = _record_text(record)
        lines.append(f"- {_tier_prefix(record, authoritative_at)}{text}")
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
    "filter_recall_records",
    "render_recall_block",
    "build_store_payload",
    "memory_subject",
]
