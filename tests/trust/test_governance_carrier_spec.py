"""L1 (Deterministic Foundations), Protocol A — the governance carrier spec.

Per ``research/tdd_agentic_systems_prompt.md``:
  - Pattern 1 (property-based schema): round-trip + frozen-ness.
  - A3 (enum-completeness): every WorkflowPhase value is mapped; no required carrier
    names a value outside the wire vocabulary.
  - A1 (schema pair): a valid spec is accepted; a malformed one is rejected.
  - Failure paths first.
Pure, deterministic, <10s, every commit. No I/O, no LLM, no mocks.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from trust.governance_carrier_spec import (
    ALL_PHASE_VALUES,
    SPEC_VERSION,
    AgentShape,
    CarrierRequirement,
    Pillar,
    PillarCarrierSpec,
    RunShape,
    default_spec,
)


class TestDefaultSpecFailurePaths:
    """Rejections first: what the spec MUST refuse to mis-report."""

    def test_fresh_run_missing_task_started_requires_identity(self):
        spec = default_spec()
        reqs = spec.required_for(
            "initialization", tool_failed=False, run_shape=RunShape.FROM_STEP_ZERO
        )
        assert [r.pillar for r in reqs] == [Pillar.IDENTITY], (
            "A fresh INITIALIZATION must require the Identity (task_started) carrier"
        )

    def test_resumed_run_does_not_require_identity(self):
        """The SKILL.md UNVERIFIABLE exemption (GG-4) — a guaranteed false-positive."""
        spec = default_spec()
        reqs = spec.required_for(
            "initialization", tool_failed=False, run_shape=RunShape.RESUMED
        )
        assert reqs == (), (
            "A resumed run must NOT require Identity — it is UNVERIFIABLE, not a FAIL"
        )

    def test_failed_tool_requires_error_occurred(self):
        spec = default_spec()
        reqs = spec.required_for(
            "tool_execution", tool_failed=True, run_shape=RunShape.FROM_STEP_ZERO
        )
        assert [r.pillar for r in reqs] == [Pillar.VALIDATION]
        assert reqs[0].event_value == "error_occurred", (
            "A failed tool must require an error_occurred carrier (silent-failure guard)"
        )

    def test_clean_tool_pass_requires_nothing(self):
        """Clean passes stay quiet (SKILL.md) — no error_occurred demanded."""
        spec = default_spec()
        reqs = spec.required_for(
            "tool_execution", tool_failed=False, run_shape=RunShape.FROM_STEP_ZERO
        )
        assert reqs == (), "A clean tool pass must not demand an error_occurred carrier"

    def test_unknown_phase_yields_no_requirements(self):
        """An unmapped phase string must not raise — it carries no requirement."""
        spec = default_spec()
        assert (
            spec.required_for(
                "not_a_phase", tool_failed=True, run_shape=RunShape.RESUMED
            )
            == ()
        )


class TestEnumCompleteness:
    """A3 — the spec accounts for every phase and only the real vocabulary."""

    def test_every_phase_value_is_mapped(self):
        spec = default_spec()
        assert set(spec.requirements.keys()) == set(ALL_PHASE_VALUES), (
            "Every WorkflowPhase value must be a key (possibly empty) — no phase "
            "may be silently unmapped"
        )

    def test_no_requirement_names_an_empty_event(self):
        spec = default_spec()
        for phase, reqs in spec.requirements.items():
            for req in reqs:
                assert req.event_value, f"{phase} requirement has an empty event_value"

    def test_spec_covers_exactly_the_four_pillars(self):
        """Drift guard (rubric side) — SKILL.md defines exactly four pillars."""
        spec = default_spec()
        assert spec.pillars == {
            Pillar.RECORDING,
            Pillar.IDENTITY,
            Pillar.VALIDATION,
            Pillar.REASONING,
        }


class TestSchemaProperties:
    """Pattern 1 — round-trip, frozen-ness, version pin."""

    def test_spec_round_trips(self):
        spec = default_spec()
        rebuilt = PillarCarrierSpec.model_validate(spec.model_dump())
        assert rebuilt == spec

    def test_spec_is_frozen(self):
        spec = default_spec()
        with pytest.raises(ValidationError):
            spec.spec_version = 99  # type: ignore[misc]

    def test_requirement_is_frozen(self):
        req = CarrierRequirement(pillar=Pillar.IDENTITY, event_value="task_started")
        with pytest.raises(ValidationError):
            req.event_value = "tampered"  # type: ignore[misc]

    def test_spec_version_pinned(self):
        assert default_spec().spec_version == SPEC_VERSION


class TestCoachShape:
    """Subject-Coach design §13.4 — the coach-shape rubric amendment, spec v2.

    ADR-0009: nothing judge-related runs inline on a coach run, so a missing
    ``eval.goal_judge`` at COMPLETION is the EXPECTED shape (the eval evidence
    is the post-hoc ``target="coach_judges"`` stream). Demanding it would be a
    guaranteed false-positive — the same class as the resumed-Identity
    exemption (GG-4). Shape-aware, never weakened: the false-positive guard
    comes first, the no-weakening guard immediately after.
    """

    def test_coach_completed_run_does_not_require_goal_judge(self):
        spec = default_spec()
        reqs = spec.required_for(
            "completion",
            tool_failed=False,
            run_shape=RunShape.FROM_STEP_ZERO,
            agent_shape=AgentShape.SUBJECT_COACH,
        )
        assert reqs == (), (
            "eval.goal_judge absent on a completed coach run is the EXPECTED "
            "shape (ADR-0009 post-hoc judges) — requiring it is a false-positive"
        )

    def test_default_shape_still_requires_goal_judge_at_completion(self):
        """The amendment must not weaken the default rubric (shape-aware,
        not weakened — the skill's resumed-run precedent)."""
        spec = default_spec()
        reqs = spec.required_for(
            "completion", tool_failed=False, run_shape=RunShape.FROM_STEP_ZERO
        )
        assert [r.event_value for r in reqs] == ["eval.goal_judge"]

    def test_coach_shape_keeps_every_other_phase_requirement(self):
        """Only the COMPLETION goal-judge rule is shape-exempt: the coach
        still owes Identity at init, the guardrail carriers, and the
        token-bearing step — its Validation posture is STRICTER, not looser."""
        spec = default_spec()
        for phase in ALL_PHASE_VALUES - {"completion"}:
            default_reqs = spec.required_for(
                phase, tool_failed=True, run_shape=RunShape.FROM_STEP_ZERO
            )
            coach_reqs = spec.required_for(
                phase,
                tool_failed=True,
                run_shape=RunShape.FROM_STEP_ZERO,
                agent_shape=AgentShape.SUBJECT_COACH,
            )
            assert coach_reqs == default_reqs, phase

    def test_agent_shape_defaults_to_default(self):
        """Back-compat: existing callers (carrier_gate) pass no agent_shape
        and must keep the full rubric."""
        spec = default_spec()
        reqs = spec.required_for(
            "completion", tool_failed=False, run_shape=RunShape.FROM_STEP_ZERO
        )
        assert len(reqs) == 1

    def test_spec_version_bumped_for_the_coach_amendment(self):
        """The rubric changed → the version must say so (a deliberate,
        reviewable diff — never a silent edit of trust data)."""
        assert SPEC_VERSION == 2


class TestDeterminism:
    """Check 7 — identical output across repeated construction."""

    def test_default_spec_is_stable(self):
        assert default_spec() == default_spec()
        for _ in range(10):
            assert default_spec().requirements == default_spec().requirements
