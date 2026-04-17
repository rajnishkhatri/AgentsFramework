"""L2 Reproducible: Contract tests for services.governance.guardrail_validator.

Contract-driven TDD, Protocol B. Failure paths first. Property-based
reinforcement ensures the regex set never flags known-clean text.
Zero LLM calls — deterministic regex only.
"""

from __future__ import annotations

import pytest

try:
    from hypothesis import given
    from hypothesis import strategies as st

    _HYPOTHESIS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dev dependency
    _HYPOTHESIS_AVAILABLE = False

from services.governance.guardrail_validator import (
    FailAction,
    GuardRail,
    GuardRailValidator,
    Severity,
    ValidationResult,
    api_key_rules,
    length_rule,
    pii_rules,
)


class TestPIIValidator:
    def test_detects_ssn(self):
        v = GuardRailValidator(pii_rules())
        results = v.validate("My SSN is 123-45-6789 please help")
        ssn = next(r for r in results if r.guardrail_name == "pii.ssn")
        assert ssn.passed is False
        assert ssn.severity == Severity.CRITICAL
        assert ssn.fail_action == FailAction.BLOCK
        assert "123-45-6789" in ssn.matches

    def test_clean_text_passes_ssn(self):
        v = GuardRailValidator(pii_rules())
        results = v.validate("The capital of France is Paris.")
        ssn = next(r for r in results if r.guardrail_name == "pii.ssn")
        assert ssn.passed is True
        assert ssn.matches == []

    def test_detects_email_flags_redact(self):
        v = GuardRailValidator(pii_rules())
        results = v.validate("Contact alice@example.com for help")
        email = next(r for r in results if r.guardrail_name == "pii.email")
        assert email.passed is False
        assert email.fail_action == FailAction.REDACT

    def test_redact_replaces_email_only(self):
        v = GuardRailValidator(pii_rules())
        redacted = v.redact("Email me at bob@foo.com please")
        assert "bob@foo.com" not in redacted
        assert "[REDACTED]" in redacted


class TestAPIKeyValidator:
    def test_flags_openai_key(self):
        v = GuardRailValidator(api_key_rules())
        results = v.validate("my key=sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456 leaked")
        oai = next(r for r in results if r.guardrail_name == "api_key.openai")
        assert oai.passed is False
        assert oai.severity == Severity.CRITICAL

    def test_flags_aws_access_key(self):
        v = GuardRailValidator(api_key_rules())
        results = v.validate("aws id=AKIAIOSFODNN7EXAMPLE please rotate")
        aws = next(r for r in results if r.guardrail_name == "api_key.aws_access")
        assert aws.passed is False

    def test_flags_github_pat(self):
        v = GuardRailValidator(api_key_rules())
        pat = "ghp_" + "A" * 36
        results = v.validate(f"token={pat} was leaked")
        gh = next(r for r in results if r.guardrail_name == "api_key.github_pat")
        assert gh.passed is False

    def test_safe_text_passes_all_api_key_rules(self):
        v = GuardRailValidator(api_key_rules())
        for r in v.validate("A perfectly normal sentence."):
            assert r.passed is True


class TestLengthRule:
    def test_long_content_warns(self):
        rule = length_rule(max_length=10)
        v = GuardRailValidator([rule])
        results = v.validate("this content is way too long")
        assert results[0].passed is False
        assert results[0].fail_action == FailAction.WARN

    def test_short_content_passes(self):
        rule = length_rule(max_length=100)
        v = GuardRailValidator([rule])
        results = v.validate("short text")
        assert results[0].passed is True


class TestValidationTrace:
    def test_trace_contains_record_per_check(self):
        v = GuardRailValidator(pii_rules())
        v.validate("alice@example.com and bob-no-ssn")
        v.validate("clean text")
        trace = v.get_validation_trace()
        assert len(trace) == len(pii_rules()) * 2
        keys = set(trace[0].keys())
        assert {"timestamp", "rule_name", "passed", "severity", "fail_action"} <= keys

    def test_reset_trace_empties_log(self):
        v = GuardRailValidator(pii_rules())
        v.validate("some content")
        assert v.get_validation_trace() != []
        v.reset_trace()
        assert v.get_validation_trace() == []


class TestValidationResultShape:
    def test_is_pydantic_model(self):
        res = ValidationResult(
            guardrail_name="x",
            passed=True,
            details="ok",
            severity=Severity.LOW,
            fail_action=FailAction.WARN,
        )
        dumped = res.model_dump()
        assert dumped["guardrail_name"] == "x"
        assert dumped["passed"] is True


# ─────────────────────────────────────────────────────────────────────
# Property-based: reinforce that clean text never triggers SSN rule.
# ─────────────────────────────────────────────────────────────────────

_clean_alphabet = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ .,!?"


if _HYPOTHESIS_AVAILABLE:

    @pytest.mark.property
    @given(st.text(alphabet=_clean_alphabet, min_size=0, max_size=500))
    def test_property_clean_text_never_triggers_ssn(clean_text):
        v = GuardRailValidator(
            [
                GuardRail(
                    name="pii.ssn",
                    description="SSN",
                    pattern=r"\b\d{3}-\d{2}-\d{4}\b",
                    severity=Severity.CRITICAL,
                    fail_action=FailAction.BLOCK,
                )
            ]
        )
        results = v.validate(clean_text)
        assert all(r.passed for r in results)
