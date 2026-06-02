"""Architecture: goal_judge_runtime_config must not import upward layers."""

from __future__ import annotations

from pathlib import Path

from utils.code_analysis import parse_imports

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent

_FORBIDDEN = {"components", "orchestration", "langgraph", "langchain", "langchain_core"}


class TestGoalJudgeRuntimeConfigIsolation:
    def test_no_upward_imports(self):
        rel_path = AGENT_ROOT / "services" / "goal_judge_runtime_config.py"
        parsed = parse_imports(rel_path)
        assert parsed["pass"], f"Could not parse {rel_path}: {parsed}"
        violations = []
        for imp in parsed["imports"]:
            module = imp["module"] or ""
            top = module.split(".")[0]
            if top in _FORBIDDEN:
                violations.append(f"line {imp['line']}: imports {module}")
        assert violations == [], (
            "services/goal_judge_runtime_config.py must not import upward:\n  "
            + "\n  ".join(violations)
        )
