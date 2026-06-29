"""L1 tests for the shared v3 frontend finding mappers (WI-6)."""

from __future__ import annotations

from code_reviewer.frontend.findings import (
    findings_from_tool,
    severity_for_rule,
)
from trust.review_schema import Severity


class TestSeverityForRule:
    def test_csp_rules_are_critical(self):
        assert severity_for_rule("CSP1") == "critical"
        assert severity_for_rule("CSP2") == "critical"

    def test_u_family_are_warning(self):
        assert severity_for_rule("U_KBD") == "warning"
        assert severity_for_rule("HARD_FAIL") == "warning"

    def test_sbx1_is_critical(self):
        assert severity_for_rule("SBX1") == "critical"

    def test_fe_ap18_patterns_are_critical(self):
        assert severity_for_rule("name~foo") == "critical"
        assert severity_for_rule("value~bar") == "critical"

    def test_unknown_defaults_to_warning(self):
        assert severity_for_rule("SOMETHING_NEW") == "warning"


class TestFindingsFromTool:
    def test_csp_strict_maps_to_fd3(self):
        raw = {
            "pass": False,
            "exit_code": 1,
            "violations": [{"rule": "CSP1", "description": "unsafe-inline"}],
        }
        findings = findings_from_tool("check_csp_strict", "frontend/middleware.ts", raw)
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_id == "FD3.CSP1"
        assert f.dimension == "FD3"
        assert f.severity == Severity.CRITICAL
        assert f.file == "frontend/middleware.ts"
        assert f.confidence == 1.0
        assert f.certificate is not None

    def test_iframe_sandbox_parses_rule_from_message(self):
        raw = {
            "pass": False,
            "exit_code": 1,
            "iframes": [
                {
                    "line": 12,
                    "violations": ["SBX1: sandbox attribute missing"],
                }
            ],
        }
        findings = findings_from_tool(
            "check_iframe_sandbox", "frontend/app/page.tsx", raw
        )
        assert len(findings) == 1
        assert findings[0].rule_id == "FD3.SBX1"
        assert findings[0].line == 12
        assert findings[0].severity == Severity.CRITICAL

    def test_secrets_emits_fd3_sec1(self):
        raw = {
            "pass": False,
            "exit_code": 1,
            "violations": [{"var": "NEXT_PUBLIC_API_KEY", "matched_pattern": "*KEY*"}],
        }
        findings = findings_from_tool(
            "check_secrets_in_public_env", "frontend/.env", raw
        )
        assert findings[0].rule_id == "FD3.SEC1"
        assert "FE-AP-18" in findings[0].description

    def test_jwt_emits_fd3_sec2(self):
        raw = {
            "pass": False,
            "exit_code": 1,
            "violations": [{"api": "localStorage", "key_or_value": "token"}],
        }
        findings = findings_from_tool("check_jwt_storage", "frontend/lib/x.ts", raw)
        assert findings[0].rule_id == "FD3.SEC2"

    def test_composer_maps_to_fd2(self):
        raw = {
            "pass": False,
            "exit_code": 1,
            "violations": [{"rule": "U_KBD", "line": 5, "description": "no keydown"}],
        }
        findings = findings_from_tool(
            "check_composer_keyboard", "frontend/Composer.tsx", raw
        )
        assert findings[0].rule_id == "FD2.U_KBD"
        assert findings[0].dimension == "FD2"
        assert findings[0].severity == Severity.WARNING

    def test_unknown_tool_returns_empty(self):
        assert findings_from_tool("not_a_real_tool", "x.ts", {"violations": []}) == []

    def test_clean_raw_returns_empty(self):
        assert (
            findings_from_tool(
                "check_csp_strict", "frontend/middleware.ts", {"violations": []}
            )
            == []
        )
