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


class TestDeterminism:
    """Check 7 — identical output across repeated construction."""

    def test_default_spec_is_stable(self):
        assert default_spec() == default_spec()
        for _ in range(10):
            assert default_spec().requirements == default_spec().requirements
