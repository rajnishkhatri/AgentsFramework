"""Architecture: components/answer_verifiers.py is a PURE Vertical-Component unit.

The deterministic answer-verifier is the authoritative half of the GoalJudge
correctness cascade. It must be dependency-free at the purity tier (no LLM, no
I/O, no framework): stdlib only, and never an upward import
(``orchestration`` / ``meta``) nor ``langgraph`` / ``langchain`` (AGENTS.md
invariants). This keeps it deterministic and trivially testable in CI.

AST-only — no imports are executed.
"""

from __future__ import annotations

from pathlib import Path

from utils.code_analysis import parse_imports

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
MODULE = "components/answer_verifiers.py"

# Pure stdlib only — the verifier deals in primitives and leaves verdict shaping
# to its caller (GoalJudge), so it does not even import components.schemas.
_ALLOWED_TOP_LEVEL = {"__future__", "re", "typing"}

_FORBIDDEN_TOP_LEVEL = {
    "langgraph",
    "langchain",
    "langchain_core",
    "langchain_community",
    "orchestration",
    "meta",
    "services",
}


class TestAnswerVerifiersLayer:
    def test_module_exists(self):
        assert (AGENT_ROOT / MODULE).is_file()

    def test_no_forbidden_imports(self):
        parsed = parse_imports(AGENT_ROOT / MODULE)
        assert parsed["pass"], parsed
        violations = [
            f"line {imp['line']}: imports {imp['module']}"
            for imp in parsed["imports"]
            if (imp["module"] or "").split(".")[0] in _FORBIDDEN_TOP_LEVEL
        ]
        assert violations == [], (
            f"{MODULE} must not import upper-layer / framework packages:\n  "
            + "\n  ".join(violations)
        )

    def test_only_stdlib_imports(self):
        parsed = parse_imports(AGENT_ROOT / MODULE)
        assert parsed["pass"], parsed
        unexpected = [
            f"line {imp['line']}: imports {imp['module']}"
            for imp in parsed["imports"]
            if (top := (imp["module"] or "").split(".")[0])
            and top not in _ALLOWED_TOP_LEVEL
        ]
        assert unexpected == [], f"{MODULE} must stay pure stdlib:\n  " + "\n  ".join(
            unexpected
        )
