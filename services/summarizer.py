"""Deterministic trajectory compaction helpers.

Legacy surface (untouched):
    CompactionResult, should_compact_trajectory, build_compaction_summary
    — kept byte-identical; consumed by orchestration/react_loop.py.

C1 surface (Phase 1 — design §4):
    MessageView, CompactionPlan, PinnedConstraint
    plan_observation_mask, plan_fold_cutoff,
    build_message_compaction, derive_pinned_floor, build_constraint_floor

This module is langchain-free by design (I-4, AGENTS.md). The MessageView
dataclass is a stdlib boundary type; the BaseMessage↔MessageView adapter lives
in orchestration/message_view.py (Phase 2). All C1 fns are pure: no I/O, no
randomness, no logging — Layer-1 deterministic per the TDD framework.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from pydantic import BaseModel


# ════════════════════════════════════════════════════════════════════════════
# Legacy surface — DO NOT MODIFY.
# Consumed by orchestration/react_loop.py and tests/services/test_reasoning_tools.py.
# ════════════════════════════════════════════════════════════════════════════


class CompactionResult(BaseModel):
    should_compact: bool
    summary_text: str
    offload_ref: str


def should_compact_trajectory(*, current_token_count: int, token_threshold: int) -> bool:
    """Return True when token pressure crosses configured threshold."""
    return current_token_count >= max(1, token_threshold)


def build_compaction_summary(
    *,
    task_input: str,
    reasoning_trace: list[str],
    tool_results: list[dict],
    latest_output: str,
) -> str:
    """Build a compact deterministic summary preserving critical context."""
    recent_trace = reasoning_trace[-3:] if reasoning_trace else []
    recent_tools = [str(item.get("tool_name", "")) for item in tool_results[-3:]]
    tools_line = ", ".join([name for name in recent_tools if name]) or "none"
    trace_line = " | ".join([entry[:120] for entry in recent_trace]) or "none"
    latest_line = (latest_output or "").strip()[:280] or "(empty)"
    task_line = (task_input or "").strip()[:200]
    return (
        "Trajectory compaction summary:\n"
        f"- task: {task_line}\n"
        f"- recent_tools: {tools_line}\n"
        f"- recent_reflection: {trace_line}\n"
        f"- latest_output: {latest_line}\n"
    )


# ════════════════════════════════════════════════════════════════════════════
# C1 surface — Phase 1 (design §4). PURE. No I/O. No langchain.
# ════════════════════════════════════════════════════════════════════════════


# Roles are stdlib strings (not an enum) so MessageView stays a plain
# dataclass and the adapter in orchestration/ can populate it from
# BaseMessage.type without an extra mapping table.
_ROLE_SYSTEM = "system"
_ROLE_HUMAN = "human"
_ROLE_AI = "ai"
_ROLE_TOOL = "tool"


@dataclass(frozen=True)
class MessageView:
    """Stdlib view of a single message. The ONLY data type the C1 pure layer touches.

    Design §3.1. The BaseMessage↔MessageView adapter (Phase 2) lives in
    orchestration/message_view.py — this module never imports langchain.

    Attributes:
        role: one of "system" | "human" | "ai" | "tool".
        content: the textual payload (may be empty).
        tool_call_id: present on role="tool" views; the id this observation answers.
        tool_calls: present on role="ai" views; a tuple of tool_call ids the
            AI view issued. Ids only (design §3.1) — block-membership is derived
            purely from id-matching against tool views' tool_call_id, so no
            richer payload is needed in the pure layer.
    """

    role: str
    content: str = ""
    tool_call_id: str | None = None
    tool_calls: tuple[str, ...] = ()


@dataclass(frozen=True)
class PinnedConstraint:
    """An atomic, verbatim, polarity-tagged constraint string.

    Design §4 fn 4 / §B2-R S3 — compound rules are split so the C2 gate is
    per-constraint. ``polarity`` is "must-do" or "must-not"; ``source`` is
    "success" (from task_understanding.success_conditions) or "user" (explicit
    constraint string).
    """

    text: str
    polarity: str
    source: str


@dataclass(frozen=True)
class CompactionPlan:
    """The pure→orchestration handoff (design §4)."""

    mask_indices: frozenset[int]
    cutoff: int
    summary: str
    pinned: tuple[PinnedConstraint, ...]
    floor_exceeded: bool


# ────────────────────────────────────────────────────────────────────────────
# Helper: walk message views into "step blocks". A step is one logical turn:
#   - a System view standing alone, OR
#   - a Human view standing alone, OR
#   - an AI view followed by zero-or-more answering Tool views (Interaction
#     Block — design §4 fn 2).
# Returned indices are message indices; the boundary list is what plan_*
# functions reason over.
# ────────────────────────────────────────────────────────────────────────────


def _block_boundaries(views: Sequence[MessageView]) -> list[tuple[int, int]]:
    """Return inclusive-exclusive (start, end) index ranges, one per logical step."""
    boundaries: list[tuple[int, int]] = []
    i = 0
    n = len(views)
    while i < n:
        v = views[i]
        if v.role == _ROLE_AI:
            j = i + 1
            while j < n and views[j].role == _ROLE_TOOL:
                j += 1
            boundaries.append((i, j))
            i = j
        else:
            boundaries.append((i, i + 1))
            i += 1
    return boundaries


# ════════════════════════════════════════════════════════════════════════════
# §4 fn 1 — plan_observation_mask
# ════════════════════════════════════════════════════════════════════════════


def plan_observation_mask(
    views: Sequence[MessageView],
    *,
    mask_after_steps: int = 10,
) -> frozenset[int]:
    """Indices of tool-observation views older than the last ``mask_after_steps`` steps.

    Reasoning/AI/human/system views are never selected. Default of 10 is the
    §B1-R R1 ablated optimum. Pure: depends only on view ordering.
    """
    blocks = _block_boundaries(views)
    if not blocks:
        return frozenset()
    keep_from_block = max(0, len(blocks) - mask_after_steps)
    selected: set[int] = set()
    for block_idx, (start, end) in enumerate(blocks):
        if block_idx >= keep_from_block:
            continue
        for msg_idx in range(start, end):
            if views[msg_idx].role == _ROLE_TOOL:
                selected.add(msg_idx)
    return frozenset(selected)


# ════════════════════════════════════════════════════════════════════════════
# §4 fn 2 — plan_fold_cutoff (bidirectional Interaction-Block walk-back).
# ════════════════════════════════════════════════════════════════════════════


def plan_fold_cutoff(
    views: Sequence[MessageView],
    *,
    keep_last_k: int,
) -> int:
    """The safe cutoff index — never splits an Interaction Block.

    Returns ``cutoff`` such that ``views[cutoff:]`` is a valid suffix:
      - it preserves the last ``keep_last_k`` step-blocks (at least), AND
      - it never leaves an orphaned tool view, AND
      - it never leaves an AI view whose answering tool view was dropped.

    A return of 0 means "do not fold". Design §4 fn 2.
    """
    n = len(views)
    if n == 0 or keep_last_k <= 0:
        return 0
    blocks = _block_boundaries(views)
    if not blocks:
        return 0
    if keep_last_k >= len(blocks):
        return 0
    # Boundary of the K-th-from-the-end step block is the cutoff candidate.
    target_block = blocks[len(blocks) - keep_last_k]
    cutoff = target_block[0]
    # The boundary list is already block-aligned (Interaction Blocks are atomic
    # by construction) — cutoff lands on a block start, so no walk-back needed.
    # The bidirectional invariant is preserved structurally.
    if cutoff < 0:
        return 0
    if cutoff >= n:
        return 0
    return cutoff


# ════════════════════════════════════════════════════════════════════════════
# §4 fn 3 — build_message_compaction (bucket schema + verbatim PINNED).
# ════════════════════════════════════════════════════════════════════════════


_BUCKET_PLACEHOLDER = "(none recorded)"

# Heuristic file-path tokens for the ARTIFACTS bucket (deterministic only).
_ARTIFACT_PATH_RE = re.compile(r"(/[\w./-]+|[\w./-]+\.(?:py|md|json|yaml|yml|txt|toml))")


def build_message_compaction(
    views: Sequence[MessageView],
    *,
    keep_last_k: int,
    pinned: Sequence[PinnedConstraint],
) -> str:
    """Structured fold for the dropped prefix.

    Buckets: SESSION INTENT / SUMMARY / ARTIFACTS / NEXT STEPS / PINNED.
    Buckets the deterministic pass can't infer are rendered with a
    ``(none recorded)`` placeholder so the schema stays stable for the L1-c
    summary_non_empty gate (design §8.2). Pinned constraints are copied
    verbatim and never summarized (design §4 fn 3 / §B2-R).
    """
    # SESSION INTENT — first human view is the closest deterministic proxy.
    intent = next(
        (v.content.strip() for v in views if v.role == _ROLE_HUMAN and v.content.strip()),
        "",
    ) or _BUCKET_PLACEHOLDER

    # SUMMARY — concatenate AI view text without prose (decisions are the AI views' contents).
    ai_texts = [v.content.strip() for v in views if v.role == _ROLE_AI and v.content.strip()]
    summary = " ⋅ ".join(ai_texts[-3:]) if ai_texts else _BUCKET_PLACEHOLDER

    # ARTIFACTS — file-path-shaped tokens swept from the trajectory.
    artifacts: list[str] = []
    for v in views:
        if v.content:
            artifacts.extend(_ARTIFACT_PATH_RE.findall(v.content))
    artifacts_line = ", ".join(sorted(set(artifacts))) if artifacts else _BUCKET_PLACEHOLDER

    # NEXT STEPS — deterministic v1 has no recorded plan; placeholder by design.
    next_steps = _BUCKET_PLACEHOLDER

    # PINNED — verbatim, polarity-tagged, never summarized.
    if pinned:
        pinned_lines = "\n".join(f"  - [{pc.polarity}] {pc.text}" for pc in pinned)
    else:
        pinned_lines = f"  {_BUCKET_PLACEHOLDER}"

    return (
        "SESSION INTENT:\n"
        f"  {intent}\n"
        "SUMMARY:\n"
        f"  {summary}\n"
        "ARTIFACTS:\n"
        f"  {artifacts_line}\n"
        "NEXT STEPS:\n"
        f"  {next_steps}\n"
        "PINNED:\n"
        f"{pinned_lines}\n"
    )


# ════════════════════════════════════════════════════════════════════════════
# §4 fn 4 — derive_pinned_floor (atomic + verbatim + polarity-tagged).
# ════════════════════════════════════════════════════════════════════════════


# Tokens that flip polarity from "must-do" → "must-not" when present anywhere
# in the constraint string. Case-insensitive for the *detection* of polarity
# only; the constraint text itself is preserved verbatim with original case.
_NEGATIVE_MARKERS = ("never", "do not", "don't", "must not", "no ", "avoid", "forbid")

# Conjunctions that signal a compound constraint must be split (§B2-R S3).
_COMPOUND_SPLIT_RE = re.compile(r"\s+and\s+", re.IGNORECASE)


def _classify_polarity(text: str) -> str:
    lowered = text.lower()
    for marker in _NEGATIVE_MARKERS:
        if marker in lowered:
            return "must-not"
    return "must-do"


def _atomize(text: str) -> list[str]:
    parts = [p.strip() for p in _COMPOUND_SPLIT_RE.split(text) if p.strip()]
    return parts or [text]


def derive_pinned_floor(
    success_conditions: Iterable[str],
    user_constraints: Iterable[str],
) -> tuple[PinnedConstraint, ...]:
    """Atomic, verbatim, polarity-tagged constraint objects (design §4 fn 4)."""
    out: list[PinnedConstraint] = []
    for raw in success_conditions:
        for atom in _atomize(raw):
            out.append(
                PinnedConstraint(
                    text=atom,
                    polarity=_classify_polarity(atom),
                    source="success",
                )
            )
    for raw in user_constraints:
        # If the source string is negative, every split-off atom inherits the
        # negative polarity even if the atom itself dropped the marker
        # ("do not delete files and modify configs" → both atoms must-not).
        source_polarity = _classify_polarity(raw)
        for atom in _atomize(raw):
            polarity = source_polarity if source_polarity == "must-not" else _classify_polarity(atom)
            out.append(PinnedConstraint(text=atom, polarity=polarity, source="user"))
    return tuple(out)


# ════════════════════════════════════════════════════════════════════════════
# §4 fn 5 — build_constraint_floor (tail re-injection, must-not by default).
# ════════════════════════════════════════════════════════════════════════════


def build_constraint_floor(
    pinned: Sequence[PinnedConstraint],
    *,
    polarity_filter: str = "must-not",
) -> str:
    """Compact verbatim string of pinned constraints for tail re-injection.

    Filtered to the ``polarity_filter`` polarity (default "must-not" — the
    fragile class per §B2-R S1). Pure; rendered independently of compaction.
    """
    selected = [pc for pc in pinned if pc.polarity == polarity_filter]
    if not selected:
        return ""
    body = "\n".join(f"- {pc.text}" for pc in selected)
    header = "Constraint floor (must-not):" if polarity_filter == "must-not" else "Constraint floor:"
    return f"{header}\n{body}\n"


# ════════════════════════════════════════════════════════════════════════════
# C2 — Phase 8: L1 deterministic gates (design §8.0 / §8.2).
#
# Five per-criterion checks, clone-shape of ``ValidationResult`` with the
# discriminator renamed ``criterion``. Computed in the §5.1 fold BEFORE the
# rewrite commits; any ``passed=False`` ⇒ decline the fold + stamp the
# failing criterion on the §7 carrier (the audit reads the decline through
# the carrier's ``floor_exceeded=True`` flag, not a separate wire).
#
# These are STRUCTURAL invariants — substring, count, graph-shape. They run
# in CI and inline on every live fold; no LLM is invoked at L1.
# ════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CompactionCriterionResult:
    """Per-criterion L1 result.

    Mirrors ``services/governance/guardrail_validator.py:56`` ``ValidationResult``
    with the discriminator renamed ``criterion`` (the design §8.2 rename).
    ``severity`` is a string literal so the §7 Recording carrier can pass it
    through ``details`` unmodified — the content-free posture forbids enums
    on the wire.
    """

    criterion: str
    passed: bool
    details: str
    severity: str = "critical"
    matches: list[str] = field(default_factory=list)


# L1-a whitespace normalization: collapse internal whitespace runs + strip.
# Applied to BOTH sides of the substring comparison (design §8.2 L1-a note).
# Case is NEVER folded — see design §8.2 "whitespace yes, case NO" callout.
_L1A_WS_RUN = re.compile(r"\s+")


def _l1a_normalize(text: str) -> str:
    return _L1A_WS_RUN.sub(" ", text).strip()


def check_pinned_substring_present(
    pinned: Sequence[PinnedConstraint],
    post_fold_text: str,
) -> CompactionCriterionResult:
    """L1-a — every pinned constraint is a substring of the post-fold text,
    whitespace-normalized, case-SENSITIVE (design §8.2 / R10).

    The action-triggering class: a silently dropped pinned ``must-not`` is
    the worst-class fold defect (§8.0).
    """
    if not pinned:
        return CompactionCriterionResult(
            criterion="pinned_substring_present",
            passed=True,
            details="no pinned constraints; vacuously passed",
        )
    haystack = _l1a_normalize(post_fold_text)
    dropped: list[str] = []
    for pc in pinned:
        needle = _l1a_normalize(pc.text)
        if needle not in haystack:
            dropped.append(pc.text)
    if dropped:
        return CompactionCriterionResult(
            criterion="pinned_substring_present",
            passed=False,
            details=f"{len(dropped)} constraint(s) dropped: " + "; ".join(dropped),
            matches=dropped,
        )
    return CompactionCriterionResult(
        criterion="pinned_substring_present",
        passed=True,
        details=f"{len(pinned)} constraint(s) preserved",
    )


def check_summary_non_empty(summary: str) -> CompactionCriterionResult:
    """L1-b — fold summary non-empty (Gemini-CLI
    ``COMPRESSION_FAILED_EMPTY_SUMMARY``, §B1-R R5)."""
    if summary and summary.strip():
        return CompactionCriterionResult(
            criterion="summary_non_empty",
            passed=True,
            details=f"summary length {len(summary)}",
        )
    return CompactionCriterionResult(
        criterion="summary_non_empty",
        passed=False,
        details="empty or whitespace-only summary",
    )


def check_tokens_reduced(
    *, tokens_before: int, tokens_after: int
) -> CompactionCriterionResult:
    """L1-c — strict inequality: a fold that doesn't reduce tokens is no fold.

    Observable span (R10): both numbers are the same the §7 carrier emits.
    """
    if tokens_after < tokens_before:
        return CompactionCriterionResult(
            criterion="tokens_reduced",
            passed=True,
            details=f"tokens_before={tokens_before} > tokens_after={tokens_after}",
        )
    return CompactionCriterionResult(
        criterion="tokens_reduced",
        passed=False,
        details=f"tokens_before={tokens_before} <= tokens_after={tokens_after}",
    )


def check_no_orphaned_tool(
    views: Sequence[MessageView],
) -> CompactionCriterionResult:
    """L1-d — bidirectional Interaction-Block check on the post-fold suffix.

    Two orphan classes (design §4 fn 2):
    (a) a ToolMessage whose ``tool_call_id`` doesn't match any AI's
        ``tool_calls`` in the suffix;
    (b) an AI ``tool_call`` whose answering ToolMessage was dropped (a
        split parallel block) — frontier-API 400 surface.

    SystemMessages don't participate in blocks (the §8.2 system-interleaved
    row).
    """
    ai_tool_call_ids: set[str] = set()
    tool_msg_ids: set[str] = set()
    for v in views:
        if v.role == _ROLE_AI and v.tool_calls:
            for tcid in v.tool_calls:
                ai_tool_call_ids.add(tcid)
        elif v.role == _ROLE_TOOL and v.tool_call_id:
            tool_msg_ids.add(v.tool_call_id)

    # (a) tool messages with no issuing AI tool_call
    orphan_tools = sorted(tool_msg_ids - ai_tool_call_ids)
    # (b) AI tool_calls with no answering tool message
    orphan_calls = sorted(ai_tool_call_ids - tool_msg_ids)

    if not orphan_tools and not orphan_calls:
        return CompactionCriterionResult(
            criterion="no_orphaned_tool",
            passed=True,
            details="all interaction blocks complete",
        )
    parts: list[str] = []
    if orphan_tools:
        parts.append("tool without AI: " + ", ".join(orphan_tools))
    if orphan_calls:
        parts.append("AI without tool: " + ", ".join(orphan_calls))
    return CompactionCriterionResult(
        criterion="no_orphaned_tool",
        passed=False,
        details=" | ".join(parts),
        matches=orphan_tools + orphan_calls,
    )


def check_floor_not_exceeded_silently(
    *, floor_exceeded: bool, fold_committed: bool
) -> CompactionCriterionResult:
    """L1-e — the inviolable-floor gate (§B2-R S4).

    ``floor_exceeded ⇒ fold declined``. Rewriting the message history when
    the floor is exceeded would silently drop a ``must-not`` constraint —
    exactly the action-triggering class of the C1 eval (§8.0).
    """
    if floor_exceeded and fold_committed:
        return CompactionCriterionResult(
            criterion="floor_not_exceeded_silently",
            passed=False,
            details="floor exceeded but rewrite committed (silent drop)",
        )
    return CompactionCriterionResult(
        criterion="floor_not_exceeded_silently",
        passed=True,
        details=(
            "floor not exceeded" if not floor_exceeded else "fold declined as required"
        ),
    )


def collect_compaction_l1(
    *,
    pinned: Sequence[PinnedConstraint],
    summary: str,
    tokens_before: int,
    tokens_after: int,
    preserved_views: Sequence[MessageView],
    floor_exceeded: bool,
    fold_committed: bool,
) -> tuple[CompactionCriterionResult, ...]:
    """Run all five L1 gates; return their results in stable order.

    Live-wire contract: ``any(not r.passed for r in result) ⇒ decline fold``
    (design §8.2 ``Live wiring`` paragraph).
    """
    return (
        check_pinned_substring_present(pinned, summary),
        check_summary_non_empty(summary),
        check_tokens_reduced(tokens_before=tokens_before, tokens_after=tokens_after),
        check_no_orphaned_tool(preserved_views),
        check_floor_not_exceeded_silently(
            floor_exceeded=floor_exceeded, fold_committed=fold_committed
        ),
    )
