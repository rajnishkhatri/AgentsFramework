"""Decompose-or-decline supervisor component (T3 fan-out decision).

The single load-bearing vertical piece of T3 (Phase 4): given the *existing*
T1 ``PlanArtifact``, decide whether the task has >= 2 genuinely independent
branches worth fanning out — or, in the safe default, **decline** and let it
run as a normal sequential T1 plan.

Why this is biased to decline. The published evidence (GAIA
single-agent-beats-multi-agent; plan §3.5a) says fanning out a
*sequentially-dependent* task is actively harmful: a downstream branch runs on
missing inputs → information loss → wrong answer. So the component's most
important job is *declining*, and a missed fan-out is the cheap error (it just
runs sequentially) while a wrong fan-out is the expensive one. The default
return on every path that is not an explicit, validated, multi-branch
independent plan is ``decline``.

Layer authority (AGENTS.md AP-5 / INV-6; component spec "Layer authority"):
pure ``components/`` — no ``langgraph`` / ``orchestration`` / ``AgentState``
import, no I/O, no sibling-component import (no V→V). The decompose LLM, if
used, is an injected ``generate`` callable, exactly like
``build_plan_artifact_llm``'s. Verified by
``tests/architecture/test_dependency_rules.py::TestSupervisorPlanLayerPurity``.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

FanoutDecision = Literal["fan_out", "decline"]
PlanningDepth = Literal["L0", "L1", "L2"]


class Delegation(BaseModel):
    """One independent branch the supervisor wants to dispatch.

    Maps 1:1 onto the existing delegation envelope
    (``DelegationDispatchRequest`` / ``TaskToolInput`` delegate inputs), so the
    worker node hands a ``Delegation`` straight to the dispatcher with no
    translation.
    """

    branch_id: int  # contiguous from 1 (MECE check)
    objective: str = Field(min_length=1, max_length=400)  # == TaskToolInput.objective
    subagent_type: str = Field(min_length=1, max_length=80)
    constraints: list[str] = Field(default_factory=list)
    expected_output_schema: dict = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)  # branch_ids needed FIRST


class SupervisorPlan(BaseModel):
    decision: FanoutDecision
    branches: list[Delegation] = Field(default_factory=list)
    reason: str  # the carrier text (why fan-out / why decline)


# ── Sequencing markers (component spec §3a) ───────────────────────────────
#
# T3 INVERTS the router/plan_builder sequencing vocabulary: the markers that
# *promote* depth there ("and then" / ", then" — router.py:226;
# plan_builder.py:46-55) are exactly the markers that say "these steps are
# DEPENDENT → decline" here. We reuse the vocabulary with the sign flipped, NOT
# the modules (LP-2 forbids importing a sibling component) — the regexes are
# deliberately re-declared so this stays a pure, self-contained vertical.

# Signal 1a — explicit sequencing (the router's own sequenced-multistep set).
_EXPLICIT_SEQUENCING = re.compile(
    r"\b(?:and then|,\s*then|then|next|after that|afterwards?|once\b|finally)\b",
    flags=re.IGNORECASE,
)

# Signal 1b — result back-reference: step N consumes step <N's output. Two
# shapes: (i) explicit "use the result of the prior step", and (ii) a definite/
# demonstrative reference to a prior step's artifact ("that flight", "the
# flight dates", "the hotel stay") — anaphora to an earlier step's output, the
# corpus `decline-trip-dated-01` / `decline-pick-then-act-06` shape.
_RESULT_BACKREF = re.compile(
    r"\b(?:use the result|use those|using those|using the|based on|"
    r"from the above|the above|the previous|those numbers|the cleaned|the new|"
    r"(?:that|the)\s+(?:flight|hotel|restaurant|file|name|trip|car|booking|"
    r"dataset|result|document|report)s?(?:\s+(?:dates?|stay|name))?)\b",
    flags=re.IGNORECASE,
)

# Signal 1c — conditional gating: step N is gated on step <N's outcome.
_CONDITIONAL_GATING = re.compile(
    r"\b(?:if\b.*\bthen\b|if eligible|if green|if the tests|otherwise)\b",
    flags=re.IGNORECASE,
)

# Join/aggregation exemption: a terminal step that collects ALL branches
# ("report all three", "summarize each result", "combine the outputs") is the
# EXPECTED shape of a fan-out — the join — not an inter-branch dependency. When
# explicit-sequencing is the only trigger on such a collective-aggregation step,
# do not treat it as sequential dependence (it would cause a missed fan-out).
# A step that references a SPECIFIC prior artifact ("that file", "those
# numbers") still trips signal 1b, so this only exempts the genuine join shape.
_JOIN_AGGREGATION = re.compile(
    r"\b(?:all (?:three|four|five|of them|the (?:results|summaries|outputs|"
    r"branches))|each (?:result|summary|output|one|of)|combine|aggregate|"
    r"report (?:all|each|the (?:results|outputs)))\b",
    flags=re.IGNORECASE,
)

# Signal 2 — path-like / artifact tokens for the shared-write check. A bare
# filename (foo.md) or an absolute workspace path; version strings like v1.2
# are not matched (need a slash or an extension that reads as a file).
_ARTIFACT_TOKEN = re.compile(
    r"(?:/[\w./-]+\.\w+|/workspace/[\w./-]+|\b[\w-]+\.(?:md|txt|csv|json|py|html|log)\b)",
    flags=re.IGNORECASE,
)

# Verbs that indicate a step *writes* its artifact (vs merely reads it). The
# shared-write race only bites when >= 2 steps WRITE the same target.
_WRITE_VERB = re.compile(
    r"\b(?:write|append|save|update|edit|overwrite|create|generate|produce)\b",
    flags=re.IGNORECASE,
)

# Lexical shared-write declaration: a single step that itself announces multiple
# writers against one target ("each append ... to the same report file"). T1's
# segmentation can collapse such a prompt into one step (the path lands on step
# 1, the section labels become bare steps 2-3), so the cross-step structural
# check below would miss it — this phrase-level catch is the backstop for the
# corpus `decline-shared-write-05` row.
_SHARED_WRITE_PHRASE = re.compile(
    r"\b(?:the same|a (?:single|shared)|one)\s+(?:\w+\s+){0,2}"
    r"(?:file|report|document|artifact|output|target|path)\b",
    flags=re.IGNORECASE,
)


def _step_goals(plan_artifact: dict[str, Any]) -> list[str]:
    """Ordered step goal strings from a T1 ``PlanArtifact.model_dump()``."""
    steps = (plan_artifact or {}).get("ordered_steps") or []
    goals: list[str] = []
    for step in steps:
        if isinstance(step, dict):
            goal = str(step.get("goal") or "").strip()
        else:
            goal = str(step).strip()
        if goal:
            goals.append(goal)
    return goals


def detect_sequential_dependence(plan_artifact: dict[str, Any]) -> bool:
    """True iff the T1 plan's steps are sequentially dependent (→ decline).

    Pure, deterministic, no LLM (component spec §3a). Runs on the common path,
    so it must be cheap and CI-testable. Two independent OR'd signals; either
    ⇒ dependent:

      Signal 1 (lexical, per step from step 2 onward) — a later step's goal
        carries an explicit-sequencing / result-back-reference / conditional-
        gating marker (the §3 "using those numbers" shape made lexical).
      Signal 2 (structural, cross-step) — two or more steps *write* the same
        artifact target; concurrent writes race even with zero back-reference
        words (the ``decline-shared-write`` corpus row, the case signal 1
        misses).

    Biased to decline (component spec §2): a borderline plan is held
    single-threaded — the safe direction. The honest limit is an unmarked
    semantic chain ("compute the budget; staff the project"): a false-negative,
    accepted for v1 by the cost asymmetry, with ``validate_independence`` as the
    second gate.
    """
    goals = _step_goals(plan_artifact)
    if len(goals) < 2:
        return False  # nothing to be sequential about (condition 1 handles <2)

    # Signal 1 — lexical back-reference / sequencing / gating in later steps.
    for goal in goals[1:]:
        # A specific prior-artifact reference or conditional gate is always a
        # dependency. Explicit sequencing alone on a collective-aggregation
        # (join) step is NOT — that is the expected fan-out terminal.
        if _RESULT_BACKREF.search(goal) or _CONDITIONAL_GATING.search(goal):
            return True
        if _EXPLICIT_SEQUENCING.search(goal) and not _JOIN_AGGREGATION.search(goal):
            return True

    # Signal 2 — shared write target. Two sub-checks:
    #  (a) structural cross-step: >= 2 steps write the same artifact token;
    #  (b) lexical phrase backstop: one step declares multiple writers against a
    #      shared target (survives T1 segmentation that strips the path).
    write_targets: dict[str, int] = {}
    for goal in goals:
        if _SHARED_WRITE_PHRASE.search(goal):
            return True
        if not _WRITE_VERB.search(goal):
            continue
        for token in _ARTIFACT_TOKEN.findall(goal):
            key = token.strip().lower()
            write_targets[key] = write_targets.get(key, 0) + 1
            if write_targets[key] >= 2:
                return True
    return False


def validate_independence(plan: SupervisorPlan) -> bool:
    """True iff the fan-out branches are genuinely independent.

    The MECE/independence gate the node trusts over the model's optimism (the
    same "structure check overrides model optimism" rule as
    ``validate_plan_mece``). Returns False if any fanned-out branch carries a
    non-empty ``depends_on`` edge, if there are < 2 branches, if branch_ids are
    not contiguous from 1, or if two branches share an objective (duplicate =
    not mutually exclusive).
    """
    if plan.decision != "fan_out":
        return False
    branches = plan.branches
    if len(branches) < 2:
        return False
    # No dependency edges among the fanned-out set.
    if any(b.depends_on for b in branches):
        return False
    # Contiguous branch_ids from 1 (MECE numbering).
    if sorted(b.branch_id for b in branches) != list(range(1, len(branches) + 1)):
        return False
    # No duplicate objectives (mutual exclusivity).
    objectives = [b.objective.strip().lower() for b in branches]
    if len(objectives) != len(set(objectives)):
        return False
    return True


def _coerce_branches(raw: Any) -> list[Delegation]:
    """Coerce an LLM ``generate`` payload into ``Delegation`` branches.

    Tolerant of the shapes a model returns: a top-level ``branches`` (or
    ``delegations`` / ``steps``) list of objects. Re-numbers ``branch_id``
    contiguously from 1 so a clean plan passes ``validate_independence``
    regardless of what the model numbered. Raises (caught by the caller's floor)
    on a non-dict or an empty branch list — no branches is not a fan-out.
    """
    if not isinstance(raw, dict):
        raise ValueError("decompose response is not a JSON object")
    items = raw.get("branches") or raw.get("delegations") or raw.get("steps")
    if not isinstance(items, list) or not items:
        raise ValueError("decompose response has no branches")
    branches: list[Delegation] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("branch entry is not an object")
        objective = str(item.get("objective") or item.get("goal") or "").strip()
        if not objective:
            raise ValueError("branch has empty objective")
        depends_on = [int(d) for d in (item.get("depends_on") or [])]
        branches.append(
            Delegation(
                branch_id=index + 1,
                objective=objective[:400],
                subagent_type=str(item.get("subagent_type") or "general").strip()[:80]
                or "general",
                constraints=[str(c) for c in (item.get("constraints") or [])],
                expected_output_schema=item.get("expected_output_schema") or {},
                depends_on=depends_on,
            )
        )
    return branches


def plan_delegations(
    *,
    task_input: str,
    plan_artifact: dict[str, Any],
    planning_depth: PlanningDepth,
    generate: Callable[[str], dict] | None = None,
) -> SupervisorPlan:
    """Decide fan-out vs decline over the EXISTING T1 plan (Protocol C).

    Does **not** re-decompose from scratch — it reads the T1 ``PlanArtifact``
    that already exists (component spec §4) and only *classifies* it. The
    decline-first decision table (component spec §2), first match wins, default
    = decline:

      1. ``planning_depth == "L0"`` OR plan has < 2 steps     → decline (single-step)
      2. ``detect_sequential_dependence`` True                → decline (sequential-dependent / GAIA guard)
      3. ``generate is None``                                 → decline (no-generator floor)
      4. LLM branches fail ``validate_independence``          → decline (not-independent)
      5. >= 2 validated independent branches                  → fan_out (independent-branches)
    """
    goals = _step_goals(plan_artifact)

    # Condition 1 — single-step floor (the §3.5a "<2, don't bother" floor).
    if planning_depth == "L0" or len(goals) < 2:
        return SupervisorPlan(
            decision="decline",
            branches=[],
            reason="single-step: nothing to parallelize (L0 or < 2 plan steps)",
        )

    # Condition 2 — sequential dependence (the GAIA guard; zero extra LLM call).
    if detect_sequential_dependence(plan_artifact):
        return SupervisorPlan(
            decision="decline",
            branches=[],
            reason="sequential-dependent: T1 plan steps reference prior outputs "
            "or share a write target (the GAIA single-agent-wins case)",
        )

    # Condition 3 — deterministic floor: absent a decompose-LLM, never invent
    # parallelism; stay single-threaded (safe).
    if generate is None:
        return SupervisorPlan(
            decision="decline",
            branches=[],
            reason="no-generator: deterministic floor declines without a "
            "decompose model",
        )

    # The model proposes branches; the structure check (not the model) decides.
    try:
        branches = _coerce_branches(generate(task_input))
    except Exception as exc:  # parse / validate failure → safe floor = decline
        return SupervisorPlan(
            decision="decline",
            branches=[],
            reason=f"no-generator: decompose failed, declining ({exc})",
        )

    candidate = SupervisorPlan(
        decision="fan_out",
        branches=branches,
        reason="independent-branches: LLM proposed parallelizable branches",
    )

    # Conditions 4 / 5 — the independence gate overrides the model's optimism.
    if not validate_independence(candidate):
        return SupervisorPlan(
            decision="decline",
            branches=[],
            reason="not-independent: proposed branches carry depends_on edges, "
            "duplicate objectives, or < 2 branches (structure check overrides "
            "model optimism)",
        )

    return candidate
