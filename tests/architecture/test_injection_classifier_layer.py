"""Architecture: injection_classifier.py stays a Layer 2 service (Sprint 3).

Asserts the frozen layer contract from
``docs/Architectures/GUARDRAILS_DIMENSION_SPACE.md`` §C:

* The new ``services/governance/injection_classifier.py`` imports ONLY
  stdlib / Pydantic / the inference runtimes (``onnxruntime`` / ``tokenizers``
  / ``numpy``) — never ``langgraph`` / ``langchain`` (AGENTS.md invariant #4)
  and never from ``components/`` / ``orchestration/`` / ``meta/`` (invariant
  #7, no upward imports).
* The optional inference runtimes are imported **lazily** (inside functions),
  so the module imports without the optional extra installed — the
  graceful-degrade contract (§D).

AST-only — no imports are executed.
"""

from __future__ import annotations

import ast
from pathlib import Path

from utils.code_analysis import parse_imports

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
MODULE = "services/governance/injection_classifier.py"

# Top-level packages the Layer 2 service is allowed to import. The inference
# runtimes are allowed because they are NOT langgraph/langchain (§C).
_ALLOWED_TOP_LEVEL = {
    "__future__",
    "importlib",
    "json",
    "logging",
    "os",
    "dataclasses",
    "enum",
    "pathlib",
    "typing",
    "collections",
    "pydantic",
    # inference runtimes (optional extra) — allowed in Layer 2
    "onnxruntime",
    "tokenizers",
    "numpy",
    # peer Layer 2 governance subpackage (self / siblings)
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


def _module_source() -> str:
    return (AGENT_ROOT / MODULE).read_text()


class TestInjectionClassifierLayer:
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

    def test_inference_runtimes_imported_lazily(self):
        """onnxruntime / tokenizers / numpy must be imported inside functions.

        A module-level import would break the graceful-degrade contract: the
        service must import even when the optional extra is absent.
        """
        tree = ast.parse(_module_source())
        runtimes = {"onnxruntime", "tokenizers", "numpy"}
        module_level = []
        for node in tree.body:  # only top-level statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in runtimes:
                        module_level.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in runtimes:
                    module_level.append(node.module)
        assert module_level == [], (
            "inference runtimes must be imported lazily (inside functions), "
            f"found module-level imports: {module_level}"
        )
