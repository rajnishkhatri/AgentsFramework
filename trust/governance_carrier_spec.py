"""Governance carrier spec — the inline four-pillar rubric, as pure trust data.

This is the **oracle** for the governance-trace enforcement gate: a transcription
of ``docs/skills/governance-trace-audit/SKILL.md`` (Steps 2-3) into a versioned,
dependency-free contract. Given the phase that just ended and the carriers
recorded during it, the gate (``services/governance/carrier_gate.py``) reads this
spec to decide which **required pillar carriers** are missing.

Why this lives in ``trust/`` (AGENTS.md "Trust Kernel Rules", FOUR_LAYER dep table):
  - **Pure** — plain Pydantic data + frozen tuples, no I/O, no logging, no network.
  - **Shared** — read by ``services/governance`` (the check) and, in Phase 2, by
    ``orchestration`` (the enforce reaction). A contract both layers depend on.
  - **Stable** — it is the rubric, versioned (``SPEC_VERSION``) so it evolves with
    the skill rather than drifting silently.
  - **Dependency-free** — and critically, ``trust/`` may NOT import from
    ``services``/``governance`` (architecture invariant; see
    ``tests/architecture/test_dependency_rules.py``). The ``EventType`` and
    ``WorkflowPhase`` enums live in ``services/governance/`` and cannot be imported
    here. So this spec keys on their **string values** (the stable wire vocabulary —
    both enums are ``(str, Enum)``). A service-layer drift-guard test
    (``tests/services/test_carrier_gate.py``) asserts these strings still match the
    real enum members; if governance renames a value, that test fails loudly rather
    than the spec drifting.

The four pillars (verbatim from SKILL.md) and their carriers:
  - **Recording**  — ``step_executed`` with non-null token usage.
  - **Identity**   — ``task_started`` carrying agent_name/version/facts_id.
  - **Validation** — ``guardrail_checked`` (+ ``error_occurred`` iff a tool failed).
  - **Reasoning**  — ``model_selected`` (rationale+decision_id) / ``step_planned`` /
    ``eval.goal_judge`` on completed runs.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# Bump when the rubric changes. SKILL.md remains the source of truth; the spec is a
# versioned transcription so a rubric change is a deliberate, reviewable diff.
SPEC_VERSION = 1


class Pillar(str, Enum):
    """The four governance pillars (SKILL.md Step 2). Names are the contract."""

    RECORDING = "recording"
    IDENTITY = "identity"
    VALIDATION = "validation"
    REASONING = "reasoning"


class RunShape(str, Enum):
    """How a run began — gates the Identity exemption (SKILL.md Step 3).

    A run replayed from a checkpoint never re-emits ``task_started``; its lowest
    recorded step is > 0. Per the skill, a missing Identity carrier on such a run is
    **UNVERIFIABLE, not a FAIL** — warning on it would be a guaranteed false-positive
    (GG-4). ``FROM_STEP_ZERO`` is a fresh run where Identity is genuinely required.
    """

    FROM_STEP_ZERO = "from_step_zero"
    RESUMED = "resumed"


# ── Wire vocabulary (string values mirrored from services/governance, drift-guarded)
# These MUST equal the ``.value`` of the corresponding EventType / WorkflowPhase
# members. We cannot import those enums (upward dependency); the service drift-guard
# test asserts equality. Centralised here so a transcription typo is caught once.

# EventType values (services/governance/black_box.py)
EVT_TASK_STARTED = "task_started"
EVT_STEP_PLANNED = "step_planned"
EVT_STEP_EXECUTED = "step_executed"
EVT_MODEL_SELECTED = "model_selected"
EVT_ERROR_OCCURRED = "error_occurred"
EVT_GUARDRAIL_CHECKED = "guardrail_checked"

# A non-EventType carrier the rubric also names (an eval-overlay span, not a
# black-box EventType). Recorded as a string token the same way.
EVT_GOAL_JUDGE = "eval.goal_judge"

# WorkflowPhase values (services/governance/phase_logger.py)
PH_INITIALIZATION = "initialization"
PH_INPUT_VALIDATION = "input_validation"
PH_ROUTING = "routing"
PH_MODEL_INVOCATION = "model_invocation"
PH_TOOL_EXECUTION = "tool_execution"
PH_EVALUATION = "evaluation"
PH_CONTINUATION = "continuation"
PH_OUTPUT_VALIDATION = "output_validation"
PH_COMPLETION = "completion"

# The complete set of phase values the spec must account for — enum-completeness
# (TDD A3): every WorkflowPhase maps to a (possibly empty) requirement set. The
# drift-guard test asserts this equals the real WorkflowPhase value set.
ALL_PHASE_VALUES: frozenset[str] = frozenset(
    {
        PH_INITIALIZATION,
        PH_INPUT_VALIDATION,
        PH_ROUTING,
        PH_MODEL_INVOCATION,
        PH_TOOL_EXECUTION,
        PH_EVALUATION,
        PH_CONTINUATION,
        PH_OUTPUT_VALIDATION,
        PH_COMPLETION,
    }
)


class CarrierRequirement(BaseModel):
    """One required pillar carrier at one phase boundary.

    ``conditional_on_tool_failure``: the carrier is required only when a tool failed
    during the phase (the Validation ``error_occurred`` rule — clean passes stay
    quiet; SKILL.md). ``exempt_when_resumed``: skip on a resumed run (the Identity
    UNVERIFIABLE exemption, GG-4).
    """

    model_config = ConfigDict(frozen=True)

    pillar: Pillar
    event_value: str = Field(
        description="EventType.value (wire string) the phase must carry."
    )
    conditional_on_tool_failure: bool = False
    exempt_when_resumed: bool = False


class PillarCarrierSpec(BaseModel):
    """Versioned phase→required-carriers map. The gate's read-only oracle."""

    model_config = ConfigDict(frozen=True)

    spec_version: int = SPEC_VERSION
    # Every phase value present (enum-completeness); empty tuple = no requirement.
    requirements: dict[str, tuple[CarrierRequirement, ...]]

    @property
    def pillars(self) -> frozenset[Pillar]:
        """All pillars the spec covers — drift-guarded against SKILL.md's four."""
        return frozenset(
            req.pillar for reqs in self.requirements.values() for req in reqs
        )

    def required_for(
        self, phase_value: str, *, tool_failed: bool, run_shape: RunShape
    ) -> tuple[CarrierRequirement, ...]:
        """Requirements in force for this phase under this run shape / failure state.

        Pure: no I/O. Applies the two SKILL.md exemptions (resumed-Identity,
        clean-pass-no-error) so the caller compares against an already-filtered set.
        """
        out: list[CarrierRequirement] = []
        for req in self.requirements.get(phase_value, ()):  # unknown phase → no reqs
            if req.exempt_when_resumed and run_shape is RunShape.RESUMED:
                continue
            if req.conditional_on_tool_failure and not tool_failed:
                continue
            out.append(req)
        return tuple(out)


def _req(
    pillar: Pillar,
    event_value: str,
    *,
    on_tool_failure: bool = False,
    exempt_resumed: bool = False,
) -> CarrierRequirement:
    return CarrierRequirement(
        pillar=pillar,
        event_value=event_value,
        conditional_on_tool_failure=on_tool_failure,
        exempt_when_resumed=exempt_resumed,
    )


def default_spec() -> PillarCarrierSpec:
    """The SKILL.md four-pillar rubric, transcribed (Step 2 + Step 3).

    Every WorkflowPhase value appears as a key (enum-completeness); phases with no
    pillar requirement (continuation, evaluation as a pass-through) map to ``()``.
    """
    requirements: dict[str, tuple[CarrierRequirement, ...]] = {
        # Identity — only at init, only on a fresh run (resumed ⇒ UNVERIFIABLE).
        PH_INITIALIZATION: (
            _req(Pillar.IDENTITY, EVT_TASK_STARTED, exempt_resumed=True),
        ),
        # Validation — the input rail must leave a check span.
        PH_INPUT_VALIDATION: (_req(Pillar.VALIDATION, EVT_GUARDRAIL_CHECKED),),
        # Reasoning — routing must record the model choice (rationale+decision_id).
        PH_ROUTING: (_req(Pillar.REASONING, EVT_MODEL_SELECTED),),
        # Recording — an LLM-invoking phase must leave a token-bearing step.
        PH_MODEL_INVOCATION: (_req(Pillar.RECORDING, EVT_STEP_EXECUTED),),
        # Validation — a failed tool MUST surface an error_occurred (silent-failure
        # guard); a clean tool pass stays quiet.
        PH_TOOL_EXECUTION: (
            _req(Pillar.VALIDATION, EVT_ERROR_OCCURRED, on_tool_failure=True),
        ),
        PH_EVALUATION: (),
        PH_CONTINUATION: (),
        # Validation — the output rail must leave a check span.
        PH_OUTPUT_VALIDATION: (_req(Pillar.VALIDATION, EVT_GUARDRAIL_CHECKED),),
        # Reasoning — a completed run must carry the goal-judge verdict
        # (the corrupt-success class the audit skill flags).
        PH_COMPLETION: (_req(Pillar.REASONING, EVT_GOAL_JUDGE),),
    }
    return PillarCarrierSpec(spec_version=SPEC_VERSION, requirements=requirements)
