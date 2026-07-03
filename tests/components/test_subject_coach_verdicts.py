"""L1 (Protocol A1 schema pairs) — GraderVerdict + PedagogyVerdict (FR-14/15/16).

Subject-Coach Phase 2 (design §7.1): both verdicts are ``components/schemas.py``
siblings of ``GoalVerdict`` and inherit its TELEMETRY-ONLY discipline. Failure
paths first (TAP-4): the rejection tests own the contract —

  - ``answer_leakage`` is FIRST-CLASS and REQUIRED. A verdict without the leak
    flag must be a ``ValidationError``, never a fail-open ``False`` default
    (a leak detector that defaults to "no leak" is worse than none).
  - Each float axis pairs with a REQUIRED binary ``*_pass`` companion (design
    gap G8): only the binaries enter κ calibration, and the judge asserts them
    directly — a silently-defaulted binary would fabricate a calibration row.
  - Float axes are schema-clamped to 0..1 (V6) — out-of-range is a rejection,
    not a silent stored value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from components.schemas import GraderVerdict, PedagogyVerdict


def _grader_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "faithfulness": 0.9,
        "correctness": 1.0,
        "justification": 0.6,
        "actionability": 0.8,
        "faithfulness_pass": True,
        "correctness_pass": True,
        "justification_pass": False,
        "actionability_pass": True,
        "rationale": "grounded in the item; the why is thin",
    }
    payload.update(overrides)
    return payload


def _pedagogy_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "mistake_identification": 0.8,
        "mistake_location": 0.7,
        "actionability": 0.9,
        "coherence": 1.0,
        "productive_struggle": 0.6,
        "illusion_of_competence": 0.5,
        "mistake_identification_pass": True,
        "mistake_location_pass": True,
        "actionability_pass": True,
        "coherence_pass": True,
        "productive_struggle_pass": False,
        "illusion_of_competence_pass": False,
        "answer_leakage": False,
        "rationale": "probed the comma splice without naming the fix",
    }
    payload.update(overrides)
    return payload


class TestPedagogyVerdictRejections:
    """Failure paths FIRST — the leak flag can never be silently absent."""

    def test_missing_answer_leakage_rejected(self):
        payload = _pedagogy_payload()
        del payload["answer_leakage"]
        with pytest.raises(ValidationError):
            PedagogyVerdict.model_validate(payload)

    def test_answer_leakage_none_rejected(self):
        with pytest.raises(ValidationError):
            PedagogyVerdict.model_validate(_pedagogy_payload(answer_leakage=None))

    def test_missing_binary_companion_rejected(self):
        payload = _pedagogy_payload()
        del payload["productive_struggle_pass"]
        with pytest.raises(ValidationError):
            PedagogyVerdict.model_validate(payload)

    def test_missing_float_axis_rejected(self):
        payload = _pedagogy_payload()
        del payload["illusion_of_competence"]
        with pytest.raises(ValidationError):
            PedagogyVerdict.model_validate(payload)

    def test_out_of_range_axis_rejected(self):
        with pytest.raises(ValidationError):
            PedagogyVerdict.model_validate(_pedagogy_payload(coherence=1.5))
        with pytest.raises(ValidationError):
            PedagogyVerdict.model_validate(_pedagogy_payload(mistake_location=-0.1))

    def test_no_aggregate_score_field_exists(self):
        """FR-16 lock: leakage is never averaged into a single quality score.

        The schema must not even offer an aggregate to average INTO — a
        reintroduced ``score``/``overall`` field is the seam this locks shut.
        """
        for banned in ("score", "overall", "quality", "average"):
            assert banned not in PedagogyVerdict.model_fields


class TestGraderVerdictRejections:
    def test_missing_float_axis_rejected(self):
        payload = _grader_payload()
        del payload["justification"]
        with pytest.raises(ValidationError):
            GraderVerdict.model_validate(payload)

    def test_missing_binary_companion_rejected(self):
        payload = _grader_payload()
        del payload["justification_pass"]
        with pytest.raises(ValidationError):
            GraderVerdict.model_validate(payload)

    def test_out_of_range_axis_rejected(self):
        with pytest.raises(ValidationError):
            GraderVerdict.model_validate(_grader_payload(faithfulness=2.0))
        with pytest.raises(ValidationError):
            GraderVerdict.model_validate(_grader_payload(correctness=-0.5))

    def test_no_aggregate_score_field_exists(self):
        for banned in ("score", "overall", "quality", "average"):
            assert banned not in GraderVerdict.model_fields


class TestAcceptance:
    """Happy paths — after the rejections, per TAP-4."""

    def test_grader_valid_roundtrip(self):
        verdict = GraderVerdict.model_validate(_grader_payload())
        rebuilt = GraderVerdict.model_validate(verdict.model_dump())
        assert rebuilt == verdict
        assert rebuilt.justification_pass is False

    def test_pedagogy_valid_roundtrip(self):
        verdict = PedagogyVerdict.model_validate(_pedagogy_payload())
        rebuilt = PedagogyVerdict.model_validate(verdict.model_dump())
        assert rebuilt == verdict
        assert rebuilt.answer_leakage is False

    def test_pedagogy_leaking_turn_carries_the_flag(self):
        verdict = PedagogyVerdict.model_validate(_pedagogy_payload(answer_leakage=True))
        assert verdict.answer_leakage is True

    def test_rationale_defaults_empty(self):
        payload = _grader_payload()
        del payload["rationale"]
        assert GraderVerdict.model_validate(payload).rationale == ""
