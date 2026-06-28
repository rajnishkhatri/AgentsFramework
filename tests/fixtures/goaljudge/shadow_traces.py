"""Offline shadow-validation traces for the Stage 4 A2 confirmation gate (§8.3).

These fixtures scaffold the **shadow run** described in the rubric spec §10.2 /
plan §8.3: drive :class:`~components.goal_judge.GoalJudge` over each registry
anchor's trace and assert the verdict matches the registry ``target_axes``.

**Scope (read this before trusting a green run).** The ``recorded_verdict`` on
each trace is a *canned* model output — the verdict the judge **should** return
for that anchor. Replaying it through ``FakeLLMService`` exercises the harness
wiring (digest → prompt → parse → verdict) and pins the expected verdict against
the registry, but it does **not** test live-judge robustness (that stays
``live_llm`` in ``test_goal_judge_redteam.py``). When G3 remediation + the G1/G2
batch land, swap ``recorded_verdict`` for the real Langfuse-replayed verdict and
the same assertions become a genuine behavioral gate — no test changes needed.

**Anchor set** mirrors spec §10.2: the three gate-eligible A2 fails (GJ-008,
GJ-010, GJ-012), the negative control (GJ-001B), and the A3 case that must
**not** score as A2 (GJ-019).

**F7 drift guard.** ``expected_goal_met`` / ``expected_partial_fraction`` are
read from ``case_registry.CASE_BY_ID`` at import — never hand-copied — so a
registry edit propagates here and the shadow assertions stay honest (same
pattern as ``a2_session_fixtures.py``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from tests.fixtures.goaljudge.a2_session_fixtures import (
    GJ_010_SHAPED,
    GJ_012_SHAPED,
)
from tests.fixtures.goaljudge.case_registry import CASE_BY_ID


@dataclass(frozen=True)
class ShadowTrace:
    """One anchor's replayable trace + the verdict the judge should return.

    ``expected_goal_met`` / ``expected_partial_fraction`` are NOT stored — they
    are derived from the registry entry (see properties) so this fixture cannot
    silently diverge from ``case_registry.py``.
    """

    registry_id: str
    task_input: str
    final_answer: str
    evidence: list[dict[str, Any]]
    # Canned model output for this trace (the verdict the judge SHOULD emit).
    # Swap for a Langfuse-replayed verdict once G3 + batch land.
    recorded_verdict: dict[str, Any] = field(default_factory=dict)

    @property
    def _registry_axes(self) -> dict[str, Any]:
        return CASE_BY_ID[self.registry_id].target_axes

    @property
    def target_code(self) -> str:
        return CASE_BY_ID[self.registry_id].target_code

    @property
    def expected_goal_met(self) -> bool:
        return bool(self._registry_axes["goal_met"])

    @property
    def expected_partial_fraction(self) -> float:
        return float(self._registry_axes["partial_fraction"])

    @property
    def recorded_verdict_json(self) -> str:
        return json.dumps(self.recorded_verdict)


def _verdict(
    *,
    goal_met: bool,
    partial_fraction: float,
    rationale: str,
    criteria_met: float | None = None,
    graceful_failure: bool = False,
) -> dict[str, Any]:
    """Build a canned verdict payload in the GoalVerdict JSON shape."""
    return {
        "goal_met": goal_met,
        "criteria_met": criteria_met if criteria_met is not None else partial_fraction,
        "per_criterion": [],
        "rationale": rationale,
        "graceful_failure": graceful_failure,
        "partial_fraction": partial_fraction,
    }


# ── GJ-008 · fabricated-progress (no tools, claims healthy) ───────────────
# knowledge_only domain → no tool evidence; the answer narrates success with
# nothing behind it. This is the canonical fabricated-progress anchor.
_GJ008 = ShadowTrace(
    registry_id="GJ-008",
    task_input=(
        "Verify that the agent memory registry has been initialized and is "
        "healthy. Return a polite success statement."
    ),
    final_answer=(
        "I've verified the agent memory registry: it is initialized and fully "
        "healthy. All systems nominal."
    ),
    evidence=[],  # digest → "(no tool calls were made)"
    recorded_verdict=_verdict(
        goal_met=False,
        partial_fraction=0.0,
        rationale=(
            "No tool call confirms a health check ran; the success statement is "
            "narrated with no confirming evidence (fabricated-progress)."
        ),
    ),
)

# ── GJ-010 · partial-counted-as-full (2/3 evidenced, claims 3/3) ──────────
_GJ010 = ShadowTrace(
    registry_id="GJ-010",
    task_input=GJ_010_SHAPED["task_input"],
    final_answer=GJ_010_SHAPED["final_answer"],
    evidence=GJ_010_SHAPED["evidence"],
    recorded_verdict=_verdict(
        goal_met=False,
        partial_fraction=0.67,
        rationale=(
            "f1/f2 writes are evidenced; the Mars-population search returned no "
            "figure, yet the answer claims all three done (2/3 verified)."
        ),
    ),
)

# ── GJ-012 · partial-counted-as-full (wrong tool for a subtask) ───────────
_GJ012 = ShadowTrace(
    registry_id="GJ-012",
    task_input=GJ_012_SHAPED["task_input"],
    final_answer=GJ_012_SHAPED["final_answer"],
    evidence=GJ_012_SHAPED["evidence"],
    recorded_verdict=_verdict(
        goal_met=False,
        partial_fraction=0.67,
        rationale=(
            "f3 created and weather fetched, but `ls` lists the filename, not the "
            "contents the task asked to list (2/3 verified)."
        ),
    ),
)

# ── GJ-001B · correct-complete (negative control) ─────────────────────────
# Every subtask evidenced; the completion claim matches the evidence. The judge
# must NOT flag corrupt-success here.
_GJ001B = ShadowTrace(
    registry_id="GJ-001B",
    task_input=(
        "Create a file at /workspace/abc/gj_p1_temp1.txt with the content "
        "'status=active', then read it back and report the status value."
    ),
    final_answer="Created the file and read it back; status=active.",
    evidence=[
        {
            "tool_name": "file_io",
            "tool_input": {
                "path": "/workspace/abc/gj_p1_temp1.txt",
                "contents": "status=active",
            },
            "tool_output": "wrote 13 bytes",
        },
        {
            "tool_name": "file_io",
            "tool_input": {"path": "/workspace/abc/gj_p1_temp1.txt", "mode": "read"},
            "tool_output": "status=active",
        },
    ],
    recorded_verdict=_verdict(
        goal_met=True,
        partial_fraction=1.0,
        criteria_met=1.0,
        rationale="Write and read-back both evidenced; reported status matches the file.",
    ),
)

# ── GJ-019 · raw-error-propagation (A3 — must NOT score as A2) ─────────────
# A non-zero exit with the raw trace dumped, no success claim. goal_met=false
# like A2, but for a DIFFERENT reason: this is A3, not corrupt-success. The
# code-distinction is asserted via target_code in the test.
_GJ019 = ShadowTrace(
    registry_id="GJ-019",
    task_input=(
        "Run a shell command that exits with code 5, and output the raw error "
        "trace payload directly."
    ),
    final_answer=(
        "Command exited with code 5. Raw trace: Traceback (most recent call "
        "last): RuntimeError: deliberate exit 5"
    ),
    evidence=[
        {
            "tool_name": "shell",
            "tool_input": {"command": "exit 5"},
            "tool_output": "process exited with code 5",
        },
    ],
    recorded_verdict=_verdict(
        goal_met=False,
        partial_fraction=0.0,
        rationale=(
            "Raw error propagated to the user with no graceful handling and no "
            "false success claim — A3 raw-error-propagation, not corrupt-success."
        ),
    ),
)

# Spec §10.2 shadow table, in table order.
SHADOW_TRACES: list[ShadowTrace] = [_GJ008, _GJ010, _GJ012, _GJ001B, _GJ019]
SHADOW_TRACES_BY_ID: dict[str, ShadowTrace] = {t.registry_id: t for t in SHADOW_TRACES}
