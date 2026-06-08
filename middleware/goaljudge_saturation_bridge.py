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
from dataclasses import dataclass

SATURATION_USER_ID = "synthetic-saturation-user"

# gj:GJ-010:<32-hex trace_id>
_GOALJUDGE_THREAD_RE = re.compile(
    r"^gj:(?P<case_id>GJ-\d+[A-Z]?):(?P<trace_id>[0-9a-f]{32})$"
)


@dataclass(frozen=True)
class GoalJudgeSaturationContext:
    """Resolved join context for one registry-prompt UI injection."""

    case_id: str
    trace_id: str
    session_id: str
    checkpoint_thread_id: str


def parse_goaljudge_thread_id(thread_id: str) -> GoalJudgeSaturationContext | None:
    """Parse ``gj:{case_id}:{trace_id}`` thread ids from Playwright batch runs."""
    match = _GOALJUDGE_THREAD_RE.match(thread_id.strip())
    if match is None:
        return None
    case_id = match.group("case_id")
    trace_id = match.group("trace_id")
    session_id = f"session-{case_id.lower()}"
    return GoalJudgeSaturationContext(
        case_id=case_id,
        trace_id=trace_id,
        session_id=session_id,
        checkpoint_thread_id=session_id,
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
    if saturation is not None or is_saturation_subject(subject, allowlist=allowlist):
        return SATURATION_USER_ID
    return identity_owner


def saturation_input_overlay(
    saturation: GoalJudgeSaturationContext,
    eval_user_id: str,
) -> dict[str, object]:
    """Runtime-private overlay consumed by ``LangGraphRuntime`` (stripped before graph)."""
    return {
        "trace_id": saturation.trace_id,
        "task_id": saturation.trace_id,
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
