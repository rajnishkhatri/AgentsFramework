"""L1 Deterministic: Tests for trust/review_schema.py -- review output models.

Schema validation (A1), defaults (A2), immutability, enum constraints,
and JSON round-trip tests (Pattern 1).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from tests.conftest import make_certificate, make_review_finding
from trust.review_schema import (
    Certificate,
    DimensionResult,
    DimensionStatus,
    ReviewFinding,
    ReviewReport,
    Severity,
    Verdict,
)

# Backwards-compatible aliases so existing test bodies keep reading
# cleanly. Prefer the ``make_certificate`` / ``make_review_finding``
# factories from ``tests.conftest`` in new code.
_make_certificate = make_certificate
_make_finding = make_review_finding


# ── Enums ──────────────────────────────────────────────────────────────


class TestSeverityEnum:
    def test_values(self):
        assert Severity.CRITICAL == "critical"
        assert Severity.WARNING == "warning"
        assert Severity.INFO == "info"

    def test_all_members(self):
        assert len(Severity) == 3


class TestVerdictEnum:
    def test_values(self):
        assert Verdict.APPROVE == "approve"
        assert Verdict.REQUEST_CHANGES == "request_changes"
        assert Verdict.REJECT == "reject"

    def test_all_members(self):
        assert len(Verdict) == 3


class TestDimensionStatusEnum:
    def test_values(self):
        assert DimensionStatus.PASS == "pass"
        assert DimensionStatus.FAIL == "fail"
        assert DimensionStatus.PARTIAL == "partial"
        assert DimensionStatus.SKIPPED == "skipped"

    def test_all_members(self):
        assert len(DimensionStatus) == 4


# ── Certificate ────────────────────────────────────────────────────────


class TestCertificate:
    def test_valid(self):
        cert = Certificate(
            premises=["[P1] check_dependency_rules: trust/models.py PASS"],
            traces=["[T1] trust/models.py imports only pydantic"],
            conclusion="D1.R1 PASS -- No upward imports found",
        )
        assert len(cert.premises) == 1
        assert cert.conclusion.startswith("D1.R1")

    def test_frozen(self):
        cert = Certificate(
            premises=["p1"],
            conclusion="PASS",
        )
        with pytest.raises(ValidationError):
            cert.conclusion = "FAIL"

    def test_traces_default_empty(self):
        cert = Certificate(premises=["p1"], conclusion="PASS")
        assert cert.traces == []

    def test_rejects_missing_premises(self):
        with pytest.raises(ValidationError):
            Certificate(conclusion="PASS")

    def test_rejects_missing_conclusion(self):
        with pytest.raises(ValidationError):
            Certificate(premises=["p1"])


# ── ReviewFinding ──────────────────────────────────────────────────────


class TestReviewFinding:
    def test_valid(self):
        finding = _make_finding()
        assert finding.rule_id == "D1.R1"
        assert finding.dimension == "D1"
        assert finding.severity == Severity.WARNING

    def test_frozen(self):
        finding = _make_finding()
        with pytest.raises(ValidationError):
            finding.rule_id = "D2.H1"

    def test_rejects_missing_rule_id(self):
        with pytest.raises(ValidationError):
            ReviewFinding(
                dimension="D1",
                severity=Severity.WARNING,
                file="test.py",
                description="desc",
                confidence=0.9,
                certificate=_make_certificate(),
            )

    def test_rejects_missing_dimension(self):
        with pytest.raises(ValidationError):
            ReviewFinding(
                rule_id="D1.R1",
                severity=Severity.WARNING,
                file="test.py",
                description="desc",
                confidence=0.9,
                certificate=_make_certificate(),
            )

    def test_rejects_missing_file(self):
        with pytest.raises(ValidationError):
            ReviewFinding(
                rule_id="D1.R1",
                dimension="D1",
                severity=Severity.WARNING,
                description="desc",
                confidence=0.9,
                certificate=_make_certificate(),
            )

    def test_confidence_bounds(self):
        _make_finding(confidence=0.0)
        _make_finding(confidence=1.0)
        with pytest.raises(ValidationError):
            _make_finding(confidence=-0.1)
        with pytest.raises(ValidationError):
            _make_finding(confidence=1.1)

    def test_line_default_none(self):
        finding = _make_finding()
        assert finding.line is None

    def test_line_set(self):
        finding = _make_finding(line=42)
        assert finding.line == 42

    def test_fix_suggestion_default_empty(self):
        finding = _make_finding()
        assert finding.fix_suggestion == ""

    def test_severity_values(self):
        for sev in Severity:
            finding = _make_finding(severity=sev)
            assert finding.severity == sev


# ── DimensionResult ────────────────────────────────────────────────────


class TestDimensionResult:
    def test_valid(self):
        result = DimensionResult(
            dimension="D1",
            name="Architectural Compliance",
            status=DimensionStatus.PASS,
        )
        assert result.dimension == "D1"
        assert result.status == DimensionStatus.PASS

    def test_frozen(self):
        result = DimensionResult(
            dimension="D1",
            name="Architectural Compliance",
            status=DimensionStatus.PASS,
        )
        with pytest.raises(ValidationError):
            result.status = DimensionStatus.FAIL

    def test_defaults(self):
        result = DimensionResult(
            dimension="D1",
            name="Architectural Compliance",
            status=DimensionStatus.PASS,
        )
        assert result.hypotheses_tested == 0
        assert result.hypotheses_confirmed == 0
        assert result.hypotheses_killed == 0
        assert result.findings == []

    def test_with_findings(self):
        finding = _make_finding()
        result = DimensionResult(
            dimension="D1",
            name="Architectural Compliance",
            status=DimensionStatus.FAIL,
            hypotheses_tested=3,
            hypotheses_confirmed=1,
            hypotheses_killed=2,
            findings=[finding],
        )
        assert len(result.findings) == 1
        assert result.findings[0].rule_id == "D1.R1"

    def test_rejects_missing_dimension(self):
        with pytest.raises(ValidationError):
            DimensionResult(name="Test", status=DimensionStatus.PASS)

    def test_rejects_missing_name(self):
        with pytest.raises(ValidationError):
            DimensionResult(dimension="D1", status=DimensionStatus.PASS)

    def test_rejects_missing_status(self):
        with pytest.raises(ValidationError):
            DimensionResult(dimension="D1", name="Test")


# ── ReviewReport ───────────────────────────────────────────────────────


class TestReviewReport:
    def test_valid_minimal(self):
        report = ReviewReport(
            verdict=Verdict.APPROVE,
            statement="All checks passed.",
            confidence=0.95,
        )
        assert report.verdict == Verdict.APPROVE
        assert report.confidence == 0.95

    def test_frozen(self):
        report = ReviewReport(
            verdict=Verdict.APPROVE,
            statement="OK",
            confidence=0.9,
        )
        with pytest.raises(ValidationError):
            report.verdict = Verdict.REJECT

    def test_defaults(self):
        report = ReviewReport(
            verdict=Verdict.APPROVE,
            statement="OK",
            confidence=0.9,
        )
        assert report.dimensions == []
        assert report.gaps == []
        assert report.validation_log == []
        assert report.files_reviewed == []
        assert report.metadata == {}

    def test_auto_timestamp(self):
        report = ReviewReport(
            verdict=Verdict.APPROVE,
            statement="OK",
            confidence=0.9,
        )
        assert isinstance(report.created_at, datetime)

    def test_confidence_bounds(self):
        ReviewReport(verdict=Verdict.APPROVE, statement="OK", confidence=0.0)
        ReviewReport(verdict=Verdict.APPROVE, statement="OK", confidence=1.0)
        with pytest.raises(ValidationError):
            ReviewReport(verdict=Verdict.APPROVE, statement="OK", confidence=-0.1)
        with pytest.raises(ValidationError):
            ReviewReport(verdict=Verdict.APPROVE, statement="OK", confidence=1.1)

    def test_rejects_missing_verdict(self):
        with pytest.raises(ValidationError):
            ReviewReport(statement="OK", confidence=0.9)

    def test_rejects_missing_statement(self):
        with pytest.raises(ValidationError):
            ReviewReport(verdict=Verdict.APPROVE, confidence=0.9)

    def test_rejects_missing_confidence(self):
        with pytest.raises(ValidationError):
            ReviewReport(verdict=Verdict.APPROVE, statement="OK")

    def test_full_report(self):
        finding = _make_finding(severity=Severity.CRITICAL, line=15)
        dim_result = DimensionResult(
            dimension="D1",
            name="Architectural Compliance",
            status=DimensionStatus.FAIL,
            hypotheses_tested=5,
            hypotheses_confirmed=1,
            hypotheses_killed=4,
            findings=[finding],
        )
        report = ReviewReport(
            verdict=Verdict.REJECT,
            statement="Rejected due to architectural violation in D1.",
            confidence=0.92,
            dimensions=[dim_result],
            gaps=["D3 not evaluated: no test files"],
            validation_log=["Phase 1: Classified 3 files"],
            files_reviewed=["trust/models.py"],
        )
        assert report.verdict == Verdict.REJECT
        assert len(report.dimensions) == 1
        assert len(report.gaps) == 1
        assert len(report.validation_log) == 1
        assert len(report.files_reviewed) == 1

    def test_verdict_values(self):
        for v in Verdict:
            report = ReviewReport(verdict=v, statement="test", confidence=0.5)
            assert report.verdict == v


# ── JSON Roundtrip (Pattern 1) ─────────────────────────────────────────


class TestRoundtrip:
    def test_certificate_roundtrip(self):
        cert = _make_certificate(
            premises=["[P1] tool output"],
            traces=["[T1] import chain"],
            conclusion="D1.R1 FAIL -- violation found",
        )
        serialized = cert.model_dump_json()
        deserialized = Certificate.model_validate_json(serialized)
        assert deserialized == cert

    def test_finding_roundtrip(self):
        finding = _make_finding(
            line=42,
            fix_suggestion="Remove the import",
        )
        serialized = finding.model_dump_json()
        deserialized = ReviewFinding.model_validate_json(serialized)
        assert deserialized.rule_id == finding.rule_id
        assert deserialized.line == 42
        assert deserialized.fix_suggestion == "Remove the import"

    def test_full_report_roundtrip(self):
        finding = _make_finding()
        dim_result = DimensionResult(
            dimension="D1",
            name="Architectural Compliance",
            status=DimensionStatus.PASS,
            findings=[finding],
        )
        report = ReviewReport(
            verdict=Verdict.APPROVE,
            statement="All checks passed.",
            confidence=0.95,
            dimensions=[dim_result],
            gaps=["D3 skipped"],
            files_reviewed=["trust/models.py"],
        )
        serialized = report.model_dump_json()
        deserialized = ReviewReport.model_validate_json(serialized)
        assert deserialized.verdict == report.verdict
        assert len(deserialized.dimensions) == 1
        assert len(deserialized.dimensions[0].findings) == 1
        assert deserialized.gaps == ["D3 skipped"]
