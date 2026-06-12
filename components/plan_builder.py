"""Planning-depth instructions and plan artifacts (framework-agnostic)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, Field

PlanningDepth = Literal["L0", "L1", "L2"]


class PlanStep(BaseModel):
    step_id: int
    title: str
    goal: str


class PlanArtifact(BaseModel):
    ordered_steps: list[PlanStep] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_conditions: list[str] = Field(default_factory=list)


class PlanValidationResult(BaseModel):
    is_valid: bool
    issues: list[str] = Field(default_factory=list)


# Sentence-period splitter: only fires on ``. `` (or trailing ``.``) when the
# following character is whitespace + uppercase OR end-of-string. This keeps
# ``/workspace/f3.txt`` and ``v1.2.3`` intact while still splitting on real
# sentence boundaries like ``"...migration. Evaluate risks..."``.
_SENTENCE_BOUNDARY = re.compile(r"\.\s+(?=[A-Z])|\.\s*$")

# Inline enumeration markers: "(1)", "(2)", "1)", "2)", "1.", "2."
# Each match becomes a split point that *follows* the marker.
_INLINE_ENUM = re.compile(r"(?:\(\s*([1-9])\s*\)|(?<![.\d])([1-9])[.)])\s+")

# Conjunction connectors that introduce a NEW imperative clause. Requires a
# leading comma — bare ``" and "`` is far too noisy (e.g. ``"trade-offs and
# risks"`` is a noun phrase, not a subtask boundary). The ``, and X``
# variant is the high-precision signal.
_CONJUNCTION_CLAUSE = re.compile(
    r",\s*(?:and|then)\s+(?=(?:also\s+)?[a-z]+\b)",
    flags=re.IGNORECASE,
)

# "X, Y, and Z" / "X, Y, then Z" — three or more imperative clauses separated
# by commas with a terminal "and"/"then". When this matches we ALSO split on
# the intermediate commas, because the trailing ``, and`` is evidence that
# the commas are subtask boundaries (not noun-phrase separators).
_COMMA_THEN_AND = re.compile(r",[^,]+,\s*(?:and|then)\s", flags=re.IGNORECASE)


def _extract_branches(task_input: str) -> list[str]:
    """Split task into ordered subtask branches.

    Splitting priority:
      1. Newlines and bullet/numbered list markers — strongest signal.
      2. Inline enumeration markers ``(1) … (2) …`` or ``1. … 2. …``.
      3. Sentence-period boundary (period followed by space + uppercase or EOS) —
         skips paths like ``/workspace/f3.txt`` and version strings ``v1.2``.
      4. Comma-or-semicolon clauses joined by ``, and `` / ``, then `` /
         ``; `` — only when the joining word introduces a new imperative
         clause (action verb leading), to avoid splitting noun phrases like
         ``"trade-offs and risks"``.
    """
    raw = (task_input or "").strip()
    if not raw:
        return ["Solve the user request directly"]

    # Stage 1 — line/list-marker splits (newlines, "1.", "- ", "• ")
    line_chunks: list[str] = []
    for chunk in re.split(r"\n+", raw):
        chunk = chunk.strip().lstrip("-•* ").strip()
        chunk = re.sub(r"^\s*\d+[.)]\s*", "", chunk)
        if chunk:
            line_chunks.append(chunk)
    if not line_chunks:
        line_chunks = [raw]

    branches: list[str] = []
    for chunk in line_chunks:
        # Stage 2 — inline enumeration "(1) X (2) Y (3) Z"
        enum_parts = _INLINE_ENUM.split(chunk)
        # _INLINE_ENUM has two capture groups; .split() includes them as
        # interleaved items. Reassemble: text segments are at even indices
        # (0, 3, 6, …) given two groups per match.
        if len(enum_parts) > 1 and any(p and p.strip().isdigit() for p in enum_parts[1::3]):
            # Keep only the textual segments between enumerators.
            text_segments = [enum_parts[0]] + enum_parts[3::3]
            stripped = [seg.strip(" ,;.") for seg in text_segments if seg and seg.strip(" ,;.")]
            if len(stripped) >= 2:
                branches.extend(stripped)
                continue

        # Stage 3 — sentence-period boundaries (path-safe)
        sentence_parts = _SENTENCE_BOUNDARY.split(chunk)
        sentence_parts = [s.strip(" \t,;.") for s in sentence_parts if s and s.strip()]
        if len(sentence_parts) >= 2:
            for s in sentence_parts:
                # Stage 4 — comma/semicolon clauses with imperative conjunctions.
                # Use semicolon as a hard split first, then "and"/"then" with
                # an action-verb lookahead.
                semicolon_parts = [p.strip(" ,;.") for p in re.split(r";\s+", s) if p.strip()]
                for sp in semicolon_parts:
                    conj_parts = _CONJUNCTION_CLAUSE.split(sp)
                    conj_parts = [p.strip(" ,;.") for p in conj_parts if p.strip()]
                    if len(conj_parts) >= 2:
                        branches.extend(conj_parts)
                    else:
                        branches.append(sp)
            continue

        # Single-sentence chunk: try semicolon + conjunction-clause split.
        for sp in (p.strip(" ,;.") for p in re.split(r";\s+", chunk) if p.strip()):
            # If "X, Y, and Z" shape is present, split on intermediate commas
            # too — the terminal ", and" is evidence that the commas are
            # imperative-clause separators, not noun-phrase joins.
            if _COMMA_THEN_AND.search(sp):
                conj_split = _CONJUNCTION_CLAUSE.split(sp)
                comma_parts: list[str] = []
                for piece in conj_split:
                    comma_parts.extend(
                        p.strip(" ,;.") for p in piece.split(",") if p.strip()
                    )
                if len(comma_parts) >= 2:
                    branches.extend(comma_parts)
                    continue
            conj_parts = _CONJUNCTION_CLAUSE.split(sp)
            conj_parts = [p.strip(" ,;.") for p in conj_parts if p.strip()]
            if len(conj_parts) >= 2:
                branches.extend(conj_parts)
            else:
                branches.append(sp)

    branches = [b for b in branches if b]
    return branches or ["Solve the user request directly"]


def compute_plan_fingerprint(
    planning_depth: PlanningDepth, artifact: PlanArtifact
) -> str:
    """Deterministic SHA-256 over the plan's identity (Phase 4, E10 dedup).

    Two consecutive plans with the same depth, ordered steps, constraints, and
    success conditions hash identically — that equality is what lets the relay
    suppress the duplicate ``step.planned`` *export* (the canonical JSONL row is
    still recorded every iteration with ``plan_changed=False``).

    Order-sensitive over ``ordered_steps`` (reordering is a different plan).
    Lives in ``components/`` (INV-6/AP-5): orchestration only calls it and
    compares the result; it owns no planning logic.
    """
    payload = {
        "planning_depth": planning_depth,
        "ordered_steps": [
            {"step_id": s.step_id, "title": s.title, "goal": s.goal}
            for s in artifact.ordered_steps
        ],
        "constraints": list(artifact.constraints),
        "success_conditions": list(artifact.success_conditions),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_plan_artifact(
    planning_depth: PlanningDepth,
    *,
    task_input: str,
) -> PlanArtifact:
    """Build a deterministic plan artifact from task input and selected depth."""
    branches = _extract_branches(task_input)
    max_steps = {"L0": 1, "L1": 3, "L2": 5}[planning_depth]
    selected = branches[:max_steps]
    steps = [
        PlanStep(step_id=index + 1, title=f"Step {index + 1}", goal=branch)
        for index, branch in enumerate(selected)
    ]
    constraints = ["Preserve user intent and requested constraints."]
    if "without" in (task_input or "").lower():
        constraints.append("Respect explicit exclusion constraints from the request.")
    return PlanArtifact(
        ordered_steps=steps,
        constraints=constraints,
        success_conditions=derive_success_conditions(branches),
    )


# Generic tail condition appended to every floor output. Matches the judge
# prompt's "supplemental constraints" framing and guarantees
# ``validate_plan_mece``'s non-empty-conditions check can never fail.
_GENERIC_TAIL_CONDITION = (
    "The final answer is internally consistent and directly responds to the request."
)

# Deliberately above the L2 depth cap: the depth cap bounds execution
# granularity, not the success definition the judge scores against.
_MAX_BRANCH_CONDITIONS = 6


def derive_success_conditions(branches: list[str]) -> list[str]:
    """Deterministic success-conditions floor (Option A).

    One observable condition per extracted branch — ALL branches, not the
    depth-truncated step slice — deduplicated, capped, plus the generic tail.
    This is the fallback the orchestration uses when the LLM-generated
    TaskUnderstanding is unavailable; it must never be empty.
    """
    conditions: list[str] = []
    seen: set[str] = set()
    for branch in branches:
        text = branch.strip()
        if not text:
            continue
        # Bare branch text: the checklist framing (judge prompt / UI card)
        # already says these are success conditions, and boilerplate prefix
        # tokens dilute the evaluator's lexical criteria_met match.
        condition = text[:160]
        key = condition.lower()
        if key in seen:
            continue
        seen.add(key)
        conditions.append(condition)
        if len(conditions) >= _MAX_BRANCH_CONDITIONS:
            break
    conditions.append(_GENERIC_TAIL_CONDITION)
    return conditions


def validate_plan_mece(plan: PlanArtifact) -> PlanValidationResult:
    """Validate plan structure and basic MECE quality checks."""
    issues: list[str] = []
    expected_step_ids = list(range(1, len(plan.ordered_steps) + 1))
    actual_step_ids = [step.step_id for step in plan.ordered_steps]
    if actual_step_ids != expected_step_ids:
        issues.append("ordered_steps must use contiguous step_id values starting at 1.")

    normalized_goals = [step.goal.strip().lower() for step in plan.ordered_steps]
    if len(normalized_goals) != len(set(normalized_goals)):
        issues.append("ordered_steps contain overlapping goals; plan is not MECE.")

    if not plan.success_conditions:
        issues.append("success_conditions must include at least one completion criterion.")

    if any(not step.goal.strip() for step in plan.ordered_steps):
        issues.append("each step must define a non-empty goal.")

    return PlanValidationResult(is_valid=not issues, issues=issues)


def build_planning_instructions(
    planning_depth: PlanningDepth,
    *,
    task_input: str,
) -> str:
    """Build system prompt addendum based on selected planning depth."""
    _ = task_input  # reserved for future heuristics/content-specific directives
    if planning_depth == "L2":
        return (
            "Planning depth L2: create a brief multi-step plan before acting, "
            "state assumptions, and validate intermediate results before final synthesis."
        )
    if planning_depth == "L1":
        return (
            "Planning depth L1: outline 2-4 concrete steps before acting, "
            "then execute in order and synthesize clearly."
        )
    return (
        "Planning depth L0: keep planning minimal, proceed directly to the most relevant "
        "action, and provide concise synthesis."
    )
