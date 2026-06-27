"""Architecture: shell_severity.py stays a Layer 2 service.

Asserts the frozen layer contract from
``docs/Architectures/GUARDRAILS_DIMENSION_SPACE.md`` §C and the plan
(``docs/plans/shell_severity_approval_hitl.plan.md`` — "Architecture
conformance (Pattern 7)"):

* ``services/governance/shell_severity.py`` imports ONLY stdlib / Pydantic /
  the ``Severity`` trust type — never ``langgraph`` / ``langchain``
  (AGENTS.md invariant #4) and never from ``components/`` / ``orchestration/`` /
  ``meta/`` (invariant #7, no upward imports).

AST-only — no imports are executed. Mirrors ``test_injection_classifier_layer``.
"""

from __future__ import annotations

from pathlib import Path

from utils.code_analysis import parse_imports

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
MODULE = "services/governance/shell_severity.py"

_ALLOWED_TOP_LEVEL = {
    "__future__",
    "logging",
    "shlex",
    "collections",
    "enum",
    "pydantic",
    # peer Layer 2 governance subpackage (Severity trust type / siblings)
    "services",
}

_FORBIDDEN_TOP_LEVEL = {
    "langgraph",
    "langchain",
    "langchain_core",
    "langchain_community",
    "components",
    "orchestration",
    "meta",
}


class TestShellSeverityLayer:
    def test_module_exists(self):
        assert (AGENT_ROOT / MODULE).is_file()

    def test_no_forbidden_imports(self):
        parsed = parse_imports(AGENT_ROOT / MODULE)
        assert parsed["pass"], parsed
        violations = []
        for imp in parsed["imports"]:
            top = (imp["module"] or "").split(".")[0]
            if top in _FORBIDDEN_TOP_LEVEL:
                violations.append(f"line {imp['line']}: imports {imp['module']}")
        assert violations == [], (
            f"{MODULE} must not import upper-layer / framework packages:\n  "
            + "\n  ".join(violations)
        )

    def test_only_allowed_top_level_imports(self):
        parsed = parse_imports(AGENT_ROOT / MODULE)
        assert parsed["pass"], parsed
        unexpected = []
        for imp in parsed["imports"]:
            top = (imp["module"] or "").split(".")[0]
            if top and top not in _ALLOWED_TOP_LEVEL:
                unexpected.append(f"line {imp['line']}: imports {imp['module']}")
        assert unexpected == [], (
            f"{MODULE} imports outside the Layer 2 allow-list:\n  "
            + "\n  ".join(unexpected)
        )

    def test_imports_only_the_severity_trust_type_from_services(self):
        """The only ``services`` dependency is the Severity trust artifact."""
        parsed = parse_imports(AGENT_ROOT / MODULE)
        services_imports = [
            imp["module"]
            for imp in parsed["imports"]
            if (imp["module"] or "").split(".")[0] == "services"
        ]
        assert services_imports == ["services.governance.guardrail_validator"], (
            services_imports
        )
