"""L1 schema tests for ``StructuredReasoning/trust/pyramid_schema``.

Failure paths first per AGENTS.md TAP-4: invalid construction is tested
before valid construction at every decision point.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from StructuredReasoning.trust import (
    AnalysisOutput,
    Branch,
    DeductiveChain,
    DeductivePremise,
    Evidence,
    GoverningThought,
    HypothesisStatus,
    IssueTree,
    KeyArgument,
    Metadata,
    OrderingType,
    Phase,
    ProblemDefinition,
    ProblemType,
    ReasoningMode,
    SoWhatChain,
    SoWhatLevel,
    ValidationCheck,
    ValidationCheckName,
    ValidationResult,
    WeaknessSeverity,
)


# ── Enums ──────────────────────────────────────────────────────────────


class TestEnumCompleteness:
    def test_phase_members(self):
        assert {p.value for p in Phase} == {
            "decompose", "hypothesize", "act", "synthesize",
        }

    def test_problem_type_members(self):
        assert {p.value for p in ProblemType} == {
            "diagnostic", "design", "evaluation", "prediction",
        }

    def test_ordering_type_members(self):
        assert {o.value for o in OrderingType} == {
            "structural", "chronological", "comparative", "degree",
        }

    def test_hypothesis_status_members(self):
        assert {h.value for h in HypothesisStatus} == {
            "confirmed", "killed", "inconclusive", "untested",
        }

    def test_reasoning_mode_members(self):
        assert {r.value for r in ReasoningMode} == {"inductive", "deductive"}

    def test_so_what_levels(self):
        assert {s.value for s in SoWhatLevel} == {
            "fact", "impact", "implication", "connection",
        }

    def test_validation_check_names(self):
        assert {v.value for v in ValidationCheckName} == {
            "completeness", "non_overlap", "item_placement", "so_what",
            "vertical_logic", "remove_one", "never_one", "mathematical",
        }

    def test_validation_result_members(self):
        assert {v.value for v in ValidationResult} == {
            "pass", "fail", "not_applicable",
        }

    def test_weakness_severity_members(self):
        assert {s.value for s in WeaknessSeverity} == {"low", "medium", "high"}


# ── ProblemDefinition (failure paths first) ────────────────────────────


class TestProblemDefinition:
    def test_rejects_empty_original_statement(self):
        with pytest.raises(ValidationError):
            ProblemDefinition(
                original_statement="",
                restated_question="Q?",
                problem_type=ProblemType.DIAGNOSTIC,
            )

    def test_rejects_invalid_problem_type(self):
        with pytest.raises(ValidationError):
            ProblemDefinition(
                original_statement="raw",
                restated_question="Q?",
                problem_type="not-a-type",  # type: ignore[arg-type]
            )

    def test_rejects_extra_field(self):
        with pytest.raises(ValidationError):
            ProblemDefinition(
                original_statement="raw",
                restated_question="Q?",
                problem_type=ProblemType.DIAGNOSTIC,
                bogus="x",  # type: ignore[call-arg]
            )

    def test_minimal_valid(self):
        pd = ProblemDefinition(
            original_statement="Sales dropped 7%.",
            restated_question="Why did fraud-detection accuracy fall by 7 points?",
            problem_type=ProblemType.DIAGNOSTIC,
        )
        assert pd.problem_type is ProblemType.DIAGNOSTIC


# ── GoverningThought ───────────────────────────────────────────────────


class TestGoverningThought:
    @pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
    def test_rejects_confidence_out_of_range(self, bad):
        with pytest.raises(ValidationError):
            GoverningThought(statement="x", confidence=bad)

    def test_rejects_empty_statement(self):
        with pytest.raises(ValidationError):
            GoverningThought(statement="", confidence=0.5)

    def test_valid(self):
        gt = GoverningThought(statement="Consolidate.", confidence=0.85)
        assert gt.confidence == 0.85


# ── KeyArgument: deductive_chain coupling ──────────────────────────────


class TestKeyArgument:
    def test_rejects_deductive_mode_without_chain(self):
        with pytest.raises(ValidationError):
            KeyArgument(
                id="arg_1",
                statement="x",
                dimension="cost",
                reasoning_mode=ReasoningMode.DEDUCTIVE,
                deductive_chain=None,
                confidence=0.8,
            )

    def test_inductive_does_not_require_chain(self):
        arg = KeyArgument(
            id="arg_1",
            statement="x",
            dimension="cost",
            reasoning_mode=ReasoningMode.INDUCTIVE,
            deductive_chain=None,
            confidence=0.8,
        )
        assert arg.deductive_chain is None

    def test_deductive_with_chain_valid(self):
        chain = DeductiveChain(
            premises=[DeductivePremise(premise="P1")],
            conclusion="C",
        )
        arg = KeyArgument(
            id="arg_1",
            statement="x",
            dimension="cost",
            reasoning_mode=ReasoningMode.DEDUCTIVE,
            deductive_chain=chain,
            confidence=0.8,
        )
        assert arg.deductive_chain is chain

    def test_rejects_chain_with_too_many_premises(self):
        with pytest.raises(ValidationError):
            DeductiveChain(
                premises=[DeductivePremise(premise=f"P{i}") for i in range(5)],
                conclusion="C",
            )


# ── Branch / IssueTree ─────────────────────────────────────────────────


class TestIssueTree:
    def test_rejects_zero_branches(self):
        with pytest.raises(ValidationError):
            IssueTree(
                root_question="Q?",
                ordering_type=OrderingType.DEGREE,
                branches=[],
            )

    def test_branch_recursive_sub_branches(self):
        leaf = Branch(id="b_1a", label="leaf", question="q?")
        parent = Branch(id="b_1", label="parent", question="q?", sub_branches=[leaf])
        tree = IssueTree(
            root_question="Q?",
            ordering_type=OrderingType.STRUCTURAL,
            branches=[parent],
        )
        assert tree.branches[0].sub_branches[0].id == "b_1a"


# ── Evidence ───────────────────────────────────────────────────────────


class TestEvidence:
    def test_rejects_empty_assigned_to(self):
        with pytest.raises(ValidationError):
            Evidence(
                id="ev_1",
                fact="f",
                source="s",
                assigned_to="",
                branch_id="b_1",
                confidence=0.5,
            )

    def test_rejects_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            Evidence(
                id="ev_1",
                fact="f",
                source="s",
                assigned_to="arg_1",
                branch_id="b_1",
                confidence=1.5,
            )


# ── ValidationCheck ────────────────────────────────────────────────────


class TestValidationCheck:
    def test_rejects_invalid_check_name(self):
        with pytest.raises(ValidationError):
            ValidationCheck(check="not-a-check", result=ValidationResult.PASS)  # type: ignore[arg-type]

    def test_not_applicable_is_valid(self):
        vc = ValidationCheck(
            check=ValidationCheckName.SO_WHAT,
            result=ValidationResult.NOT_APPLICABLE,
            details="LLM-judge deferred to PR 3",
        )
        assert vc.result is ValidationResult.NOT_APPLICABLE


# ── AnalysisOutput round-trip ──────────────────────────────────────────


def _minimal_valid_payload() -> dict:
    """Smallest valid AnalysisOutput as a dict, used by round-trip tests."""
    return {
        "problem_definition": {
            "original_statement": "Original.",
            "restated_question": "Restated?",
            "problem_type": "diagnostic",
            "scope_boundaries": "",
            "success_criteria": "",
        },
        "issue_tree": {
            "root_question": "Restated?",
            "ordering_type": "degree",
            "branches": [{
                "id": "b_1",
                "label": "data_drifts",
                "question": "Did data drift?",
                "hypothesis": "PSI > 0.2",
                "hypothesis_status": "confirmed",
                "evidence_ids": ["ev_1"],
                "sub_branches": [],
            }],
        },
        "governing_thought": {
            "statement": "Cause is data drift; retrain.",
            "confidence": 0.85,
        },
        "key_arguments": [{
            "id": "arg_1",
            "statement": "Drift is the root cause.",
            "dimension": "diagnosis",
            "reasoning_mode": "inductive",
            "evidence_ids": ["ev_1"],
            "confidence": 0.85,
            "so_what_chain": [
                {"level": "fact", "statement": "PSI rose to 0.31."},
                {"level": "impact", "statement": "Model sees novel inputs."},
                {"level": "implication", "statement": "Accuracy degrades."},
                {"level": "connection", "statement": "Retrain to recover."},
            ],
        }],
        "evidence": [{
            "id": "ev_1",
            "fact": "PSI 0.31 on day 8.",
            "source": "monitoring dashboard",
            "assigned_to": "arg_1",
            "branch_id": "b_1",
            "confidence": 0.95,
        }],
        "gaps": {
            "untested_hypotheses": [],
            "missing_data": [],
            "known_weaknesses": [],
        },
        "cross_branch_interactions": [],
        "validation_log": [{
            "check": "completeness",
            "result": "pass",
            "details": "all branches covered",
        }],
        "metadata": {
            "problem_scope": "fraud detection accuracy decline",
            "tools_used": [],
            "iteration_count": 1,
            "reasoning_trace_summary": "single-shot",
            "communication_tone": "standard",
            "presentation_notes": [],
        },
    }


class TestAnalysisOutput:
    def test_rejects_empty_key_arguments(self):
        payload = _minimal_valid_payload()
        payload["key_arguments"] = []
        with pytest.raises(ValidationError):
            AnalysisOutput.model_validate(payload)

    def test_rejects_extra_top_level_field(self):
        payload = _minimal_valid_payload()
        payload["bogus_field"] = "x"
        with pytest.raises(ValidationError):
            AnalysisOutput.model_validate(payload)

    def test_round_trip_equality(self):
        payload = _minimal_valid_payload()
        analysis = AnalysisOutput.model_validate(payload)
        round_tripped = AnalysisOutput.model_validate(analysis.to_dict())
        assert round_tripped == analysis

    def test_to_dict_returns_jsonable(self):
        analysis = AnalysisOutput.model_validate(_minimal_valid_payload())
        as_dict = analysis.to_dict()
        assert as_dict["problem_definition"]["problem_type"] == "diagnostic"
        assert isinstance(as_dict["key_arguments"], list)


class TestMetadataDefaults:
    def test_iteration_count_lower_bound(self):
        with pytest.raises(ValidationError):
            Metadata(iteration_count=0)

    def test_default_tools_used_empty(self):
        meta = Metadata()
        assert meta.tools_used == []
        assert meta.iteration_count == 1


class TestSoWhatChain:
    def test_rejects_invalid_level(self):
        with pytest.raises(ValidationError):
            SoWhatChain(level="not-a-level", statement="x")  # type: ignore[arg-type]

    def test_valid(self):
        s = SoWhatChain(level=SoWhatLevel.FACT, statement="observed")
        assert s.level is SoWhatLevel.FACT
