"""Phase 2 — BaseMessage ↔ MessageView adapter (design §3.1 / §3.2).

This is the **only** place ``langchain_core.messages.BaseMessage`` and the
stdlib ``MessageView`` meet. The pure C1 layer (``services/summarizer.py``)
operates exclusively on ``MessageView`` and is forbidden from importing
``langchain_core`` (I-4 / AGENTS.md / ``test_dependency_rules.py:104``).
Orchestration legitimately imports langchain (precedent: ``react_loop.py``,
``state.py``, ``checkpointer_wrapper.py``), so the adapter lives here.

The ``MessageView`` dataclass itself is defined in ``services/summarizer.py``
because the pure functions need to name their own data type without an import
cycle. It is re-exported here so callers can read the design's contract from
its canonical home.

Module surface (design §3.2):

* ``MessageView``      — stdlib view (re-exported)
* ``to_views(msgs)``   — list[BaseMessage] → list[MessageView]
* ``rebuild(*, summary, preserved, tail)`` — rematerialize the compacted
  transcript with optional summary header and tail-floor footer.
* ``mask_observation(msg, placeholder)`` — ToolMessage copy with content
  swapped, ``tool_call_id`` preserved (the masking-key invariant).

Phase 2 is **inert** — no caller exists yet. Wired by Phase 5 (WRITE seam)
and Phase 6 (READ seam).
"""

from __future__ import annotations

from typing import Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

# Re-export the canonical MessageView from the pure layer. Both modules
# expose the same identity so ``isinstance`` / ``is`` checks compare equal
# across the boundary.
from services.summarizer import MessageView

__all__ = ["MessageView", "to_views", "rebuild", "mask_observation"]


# ════════════════════════════════════════════════════════════════════════════
# to_views — BaseMessage → MessageView.
#
# Role mapping is by BaseMessage subclass (not by the ``type`` attribute —
# subclasses are the authoritative discriminator in this codebase). Unknown
# subclasses fall back to the BaseMessage ``type`` string so the adapter never
# silently drops a message; if a new subclass appears upstream a future
# regression test can pin the mapping rather than this adapter swallowing it.
# ════════════════════════════════════════════════════════════════════════════


def _extract_call_ids(ai: AIMessage) -> tuple[str, ...]:
    """Pull tool_call ids from an AIMessage in the shape design §3.1 expects.

    Each tool_call entry in this codebase is a dict with at least an ``id`` key
    (see ``react_loop.py:302-305`` for the canonical reader). We tolerate
    entries that are objects with ``.id`` for symmetry with the inverse
    reader pattern.
    """
    out: list[str] = []
    for tc in getattr(ai, "tool_calls", []) or []:
        tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
        if tid is not None:
            out.append(str(tid))
    return tuple(out)


def to_views(msgs: Sequence[BaseMessage]) -> list[MessageView]:
    """Adapt a list of langchain BaseMessages to stdlib MessageViews.

    Preserves order, content verbatim, and ToolMessage ↔ AI block-membership
    metadata (tool_call_id / tool_calls ids) — the data the pure planner uses
    to compute Interaction-Block-safe cutoffs.
    """
    out: list[MessageView] = []
    for msg in msgs:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if isinstance(msg, SystemMessage):
            out.append(MessageView(role="system", content=content))
        elif isinstance(msg, HumanMessage):
            out.append(MessageView(role="human", content=content))
        elif isinstance(msg, AIMessage):
            out.append(
                MessageView(
                    role="ai",
                    content=content,
                    tool_calls=_extract_call_ids(msg),
                )
            )
        elif isinstance(msg, ToolMessage):
            out.append(
                MessageView(
                    role="tool",
                    content=content,
                    tool_call_id=msg.tool_call_id,
                )
            )
        else:
            # Unknown subclass — fall back to the BaseMessage type discriminator
            # so we never silently drop. Phase 5+ tests will pin this branch if
            # ever exercised.
            out.append(MessageView(role=getattr(msg, "type", "ai"), content=content))
    return out


# ════════════════════════════════════════════════════════════════════════════
# rebuild — compacted transcript materialization.
#
# Returned shape:  [SystemMessage(summary)?, *preserved, SystemMessage(tail)?]
#
# Preserved messages are passed through by reference (not copied) so that
# downstream checkpoint id rematerialization stays predictable — rebuild is a
# layout step, not a mutation. Empty summary / tail strings are treated as
# absent (so a degenerate empty fold can't sneak past the L1-c
# summary_non_empty gate by injecting a blank SystemMessage).
# ════════════════════════════════════════════════════════════════════════════


def rebuild(
    *,
    summary: str | None,
    preserved: Sequence[BaseMessage],
    tail: str | None,
) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    if summary:
        out.append(SystemMessage(content=summary))
    out.extend(preserved)
    if tail:
        out.append(SystemMessage(content=tail))
    return out


# ════════════════════════════════════════════════════════════════════════════
# mask_observation — transient text replacement on a single ToolMessage.
#
# The masking key is ``tool_call_id`` — orphan-safety in plan_fold_cutoff and
# the Interaction-Block invariants depend on it surviving the swap. Non-tool
# messages are returned unchanged (safety; mask is a no-op on the wrong type
# rather than a raise that would have to be guarded at every caller).
# ════════════════════════════════════════════════════════════════════════════


def mask_observation(msg: BaseMessage, placeholder: str) -> BaseMessage:
    if isinstance(msg, ToolMessage):
        return ToolMessage(content=placeholder, tool_call_id=msg.tool_call_id)
    return msg
