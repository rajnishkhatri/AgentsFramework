"""GoalJudge synthetic-saturation bridge for UI batch runs (G1).

Maps Playwright-injected thread ids of the form ``gj:{case_id}:{trace_id}``
to deterministic eval-capture / Langfuse join keys used by the CLI batch:

- ``user_id`` → ``synthetic-saturation-user``
- ``task_id`` / ``workflow_id`` / ``trace_id`` → uuid5(case_id) 32-hex

Option A (subject allowlist via ``GOALJUDGE_SATURATION_SUBJECTS``) also maps
dedicated WorkOS test principals to the saturation user for telemetry when the
``gj:`` thread prefix is absent.

Pure module — no FastAPI / LangGraph imports (middleware horizontal helper).
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass

SATURATION_USER_ID = "synthetic-saturation-user"

# gj:GJ-010:<32-hex> | gj:GJ-003B:<32-hex> | gj:GJ-F-001:<32-hex> | gj:GJ-STRESS-001:<32-hex>
_GOALJUDGE_THREAD_RE = re.compile(
    r"^gj:(?P<case_id>GJ-(?:F-\d+|STRESS-\d+|\d+[A-Z]?)):(?P<trace_id>[0-9a-f]{32})$"
)

# mem:MEM-0001:s1:user0001:<32-hex>
#
# The ``mem:`` bridge is the memory multi-session corpus's thread form. Unlike
# ``gj:`` (which collapses every run to ``SATURATION_USER_ID`` — one user), it
# carries a PER-CASE ``user_id`` and a ``session_idx``. This is the seam the
# cross-user-leak guard depends on: distinct per-case user_ids must resolve to
# distinct ``eval_user_id``s, or a leak is structurally impossible to observe.
# See ``docs/plans/memory_multisession_e2e_stress.plan.md`` §9.1.
_MEM_THREAD_RE = re.compile(
    r"^mem:(?P<case_id>MEM-[0-9A-Za-z-]+):s(?P<session_idx>\d+):"
    r"(?P<user_id>[0-9A-Za-z]+):(?P<trace_id>[0-9a-f]{32})$"
)


@dataclass(frozen=True)
class GoalJudgeSaturationContext:
    """Resolved join context for one registry-prompt UI injection.

    ``user_id`` / ``session_idx`` are populated only for ``mem:`` threads (the
    memory multi-session corpus); ``gj:`` threads leave them ``None`` and
    collapse to ``SATURATION_USER_ID`` as before.
    """

    case_id: str
    trace_id: str
    session_id: str
    checkpoint_thread_id: str
    user_id: str | None = None
    session_idx: int | None = None


def parse_goaljudge_thread_id(thread_id: str) -> GoalJudgeSaturationContext | None:
    """Parse ``gj:{case_id}:{trace_id}`` thread ids from Playwright batch runs.

    ``checkpoint_thread_id`` carries a fresh per-parse suffix: like
    ``task_id`` (minted fresh by the runtime), the LangGraph checkpoint
    thread must NOT be replayed across batch reruns — a static
    ``session-gj-XXX`` thread accumulates state until the resumed graph
    ends every run immediately with an empty assistant message.
    ``session_id`` stays deterministic as the telemetry/Langfuse join key.
    """
    cleaned = thread_id.strip()

    mem_match = _MEM_THREAD_RE.match(cleaned)
    if mem_match is not None:
        case_id = mem_match.group("case_id")
        trace_id = mem_match.group("trace_id")
        session_idx = int(mem_match.group("session_idx"))
        # session_id keeps the per-session position so seed and probe traces in
        # the same case are distinct telemetry join keys.
        session_id = f"session-{case_id.lower()}-s{session_idx}"
        return GoalJudgeSaturationContext(
            case_id=case_id,
            trace_id=trace_id,
            session_id=session_id,
            checkpoint_thread_id=f"{session_id}-{uuid.uuid4().hex[:8]}",
            user_id=mem_match.group("user_id"),
            session_idx=session_idx,
        )

    match = _GOALJUDGE_THREAD_RE.match(cleaned)
    if match is None:
        return None
    case_id = match.group("case_id")
    trace_id = match.group("trace_id")
    session_id = f"session-{case_id.lower()}"
    return GoalJudgeSaturationContext(
        case_id=case_id,
        trace_id=trace_id,
        session_id=session_id,
        checkpoint_thread_id=f"{session_id}-{uuid.uuid4().hex[:8]}",
    )


def saturation_subjects_from_env() -> frozenset[str]:
    """WorkOS ``sub`` values allowed to emit saturation-scoped telemetry."""
    raw = os.environ.get("GOALJUDGE_SATURATION_SUBJECTS", "")
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def is_saturation_subject(
    subject: str,
    *,
    allowlist: frozenset[str] | None = None,
) -> bool:
    """Return True when ``subject`` is a configured saturation test principal."""
    subjects = saturation_subjects_from_env() if allowlist is None else allowlist
    return subject in subjects


def resolve_telemetry_subject(
    subject: str,
    saturation: GoalJudgeSaturationContext | None,
    *,
    allowlist: frozenset[str] | None = None,
) -> str:
    """Langfuse / telemetry ``user_id`` for this run."""
    if saturation is not None and saturation.user_id:
        # mem: bridge — per-case synthetic memory subject (cross-user-leak guard).
        return saturation.user_id
    if saturation is not None or is_saturation_subject(subject, allowlist=allowlist):
        return SATURATION_USER_ID
    return subject


def resolve_eval_user_id(
    identity_owner: str,
    saturation: GoalJudgeSaturationContext | None,
    subject: str,
    *,
    allowlist: frozenset[str] | None = None,
) -> str:
    """``configurable.user_id`` for eval_capture rows."""
    if saturation is not None and saturation.user_id:
        # mem: bridge — the per-case user_id IS the memory key the recall/store
        # seams scope on; returning it (not the shared constant) is what makes
        # the cross-user-leak guard observable.
        return saturation.user_id
    if saturation is not None or is_saturation_subject(subject, allowlist=allowlist):
        return SATURATION_USER_ID
    return identity_owner


def saturation_input_overlay(
    saturation: GoalJudgeSaturationContext,
    eval_user_id: str,
) -> dict[str, object]:
    """Runtime-private overlay consumed by ``LangGraphRuntime`` (stripped before graph).

    Deliberately does NOT carry ``task_id``. ``trace_id`` is deterministic by
    design (the Langfuse join key for replay), but ``task_id`` is a per-run
    discriminator the planner uses to scope tool-result counts. Reusing
    ``trace_id`` as ``task_id`` would make every Playwright replay of the same
    registry case look like a continuation of the prior run, which:

    - causes ``select_planning_depth`` to short-circuit to ``L0`` via the
      per-task synthesis check (``components/router.py``), capping multi-subtask
      prompts at 1 plan step
    - lets the agent fabricate subtasks 2-N because its tool-call budget runs
      out before reaching them

    The runtime defaults ``task_id`` to a fresh ``uuid.uuid4().hex`` when this
    overlay omits it — same shape as the non-saturation path — so every replay
    is treated as a fresh task by the planner. The deterministic Langfuse join
    via ``trace_id`` is unaffected.
    """
    return {
        "trace_id": saturation.trace_id,
        "user_id": eval_user_id,
        "case_id": saturation.case_id,
        "checkpoint_thread_id": saturation.checkpoint_thread_id,
    }


__all__ = [
    "SATURATION_USER_ID",
    "GoalJudgeSaturationContext",
    "is_saturation_subject",
    "parse_goaljudge_thread_id",
    "resolve_eval_user_id",
    "resolve_telemetry_subject",
    "saturation_input_overlay",
    "saturation_subjects_from_env",
]
