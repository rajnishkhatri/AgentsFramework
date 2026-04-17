"""L2 Reproducible: Tests for utils/code_analysis.py -- AST-based analysis tools.

Each test uses inline fixture files written to a temp directory.
Results are deterministic given the fixture content.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from utils.code_analysis import (
    check_dependency_rules,
    check_protocol_conformance,
    check_trust_purity,
    classify_layer,
    detect_anti_patterns,
    parse_imports,
)


# ── Helpers ────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project skeleton for testing."""
    for d in ("trust", "utils", "agents", "governance",
              "services", "components", "orchestration"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "__init__.py").write_text("")
    return tmp_path


def _write_file(project: Path, rel_path: str, content: str) -> Path:
    """Write a Python file with dedented content."""
    filepath = project / rel_path
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(textwrap.dedent(content))
    return filepath


# ── parse_imports ──────────────────────────────────────────────────────


class TestParseImports:
    def test_import_from(self, tmp_project):
        f = _write_file(tmp_project, "trust/models.py", """\
            from pydantic import BaseModel
            from trust.enums import IdentityStatus
        """)
        result = parse_imports(f)
        assert result["pass"] is True
        modules = [i["module"] for i in result["imports"]]
        assert "pydantic" in modules
        assert "trust.enums" in modules

    def test_bare_import(self, tmp_project):
        f = _write_file(tmp_project, "utils/helper.py", """\
            import ast
            import pathlib
        """)
        result = parse_imports(f)
        assert result["pass"] is True
        modules = [i["module"] for i in result["imports"]]
        assert "ast" in modules
        assert "pathlib" in modules

    def test_top_package_extracted(self, tmp_project):
        f = _write_file(tmp_project, "utils/helper.py", """\
            from trust.models import AgentFacts
        """)
        result = parse_imports(f)
        assert result["imports"][0]["top_package"] == "trust"

    def test_line_numbers(self, tmp_project):
        f = _write_file(tmp_project, "utils/helper.py", """\
            import os
            from pathlib import Path
        """)
        result = parse_imports(f)
        lines = [i["line"] for i in result["imports"]]
        assert 1 in lines
        assert 2 in lines

    def test_empty_file(self, tmp_project):
        f = _write_file(tmp_project, "trust/empty.py", "")
        result = parse_imports(f)
        assert result["pass"] is True
        assert result["imports"] == []

    def test_syntax_error(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", "def broken(:\n")
        result = parse_imports(f)
        assert result["pass"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "PARSE"

    def test_nonexistent_file(self, tmp_project):
        result = parse_imports(tmp_project / "nonexistent.py")
        assert result["pass"] is False


# ── classify_layer ─────────────────────────────────────────────────────


class TestClassifyLayer:
    def test_trust_layer(self):
        result = classify_layer("trust/models.py")
        assert result["layer"] == "Trust Foundation"
        assert result["layer_dir"] == "trust"

    def test_utils_layer(self):
        result = classify_layer("utils/code_analysis.py")
        assert result["layer"] == "Horizontal Services"
        assert result["layer_dir"] == "utils"

    def test_agents_layer(self):
        result = classify_layer("agents/code_reviewer.py")
        assert result["layer"] == "Vertical Components"
        assert result["layer_dir"] == "agents"

    def test_governance_layer(self):
        result = classify_layer("governance/lifecycle.py")
        assert result["layer"] == "Meta-Layer"
        assert result["layer_dir"] == "governance"

    def test_services_layer(self):
        result = classify_layer("services/llm_config.py")
        assert result["layer"] == "Horizontal Services"
        assert result["layer_dir"] == "services"

    def test_components_layer(self):
        result = classify_layer("components/router.py")
        assert result["layer"] == "Vertical Components"
        assert result["layer_dir"] == "components"

    def test_orchestration_layer(self):
        result = classify_layer("orchestration/react_loop.py")
        assert result["layer"] == "Orchestration"
        assert result["layer_dir"] == "orchestration"

    def test_unknown_layer(self):
        result = classify_layer("scripts/deploy.py")
        assert result["layer"] == "Unknown"
        assert result["layer_dir"] == ""

    def test_nested_paths(self):
        result = classify_layer("utils/cloud_providers/aws_identity.py")
        assert result["layer"] == "Horizontal Services"


# ── check_dependency_rules ─────────────────────────────────────────────


class TestCheckDependencyRules:
    def test_trust_clean(self, tmp_project):
        f = _write_file(tmp_project, "trust/models.py", """\
            from pydantic import BaseModel
            from trust.enums import IdentityStatus
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is True
        assert result["violations"] == []

    def test_trust_imports_utils_fails(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", """\
            from utils.helper import some_function
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert len(result["violations"]) == 1
        assert "utils" in result["violations"][0]["description"]

    def test_trust_imports_agents_fails(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", """\
            from agents.writer import Writer
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("agents" in v["description"] for v in result["violations"])

    def test_utils_clean(self, tmp_project):
        f = _write_file(tmp_project, "utils/helper.py", """\
            import ast
            from trust.models import AgentFacts
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_utils_imports_agents_fails(self, tmp_project):
        f = _write_file(tmp_project, "utils/bad.py", """\
            from agents.writer import Writer
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("agents" in v["description"] for v in result["violations"])

    def test_services_imports_trust_ok(self, tmp_project):
        f = _write_file(tmp_project, "services/llm_config.py", """\
            from trust.models import AgentFacts
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_services_imports_components_fails(self, tmp_project):
        f = _write_file(tmp_project, "services/bad.py", """\
            from components.schemas import EvalRecord
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("components" in v["description"] for v in result["violations"])

    def test_services_imports_orchestration_fails(self, tmp_project):
        f = _write_file(tmp_project, "services/bad.py", """\
            from orchestration.state import AgentState
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("orchestration" in v["description"].lower() for v in result["violations"])

    def test_components_imports_services_ok(self, tmp_project):
        f = _write_file(tmp_project, "components/router.py", """\
            from services.base_config import AgentConfig
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_components_imports_orchestration_fails(self, tmp_project):
        f = _write_file(tmp_project, "components/bad.py", """\
            from orchestration.react_loop import build_graph
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("orchestration" in v["description"].lower() for v in result["violations"])

    def test_trust_imports_services_fails(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", """\
            from services.llm_config import LLMService
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("services" in v["description"].lower() for v in result["violations"])

    def test_agents_file_not_checked(self, tmp_project):
        f = _write_file(tmp_project, "agents/reviewer.py", """\
            from utils.helper import func
            from trust.models import AgentFacts
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_multiple_violations(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", """\
            from utils.helper import func
            from agents.writer import Writer
        """)
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert len(result["violations"]) == 2


# ── check_trust_purity ─────────────────────────────────────────────────


class TestCheckTrustPurity:
    def test_pure_trust_file(self, tmp_project):
        f = _write_file(tmp_project, "trust/models.py", """\
            from __future__ import annotations
            from datetime import datetime
            from typing import Any
            from pydantic import BaseModel
        """)
        result = check_trust_purity(f)
        assert result["pass"] is True

    def test_impure_logging(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", """\
            import logging
            from pydantic import BaseModel
        """)
        result = check_trust_purity(f)
        assert result["pass"] is False
        assert any("logging" in v["description"] for v in result["violations"])

    def test_impure_os(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", """\
            import os
        """)
        result = check_trust_purity(f)
        assert result["pass"] is False

    def test_impure_requests(self, tmp_project):
        f = _write_file(tmp_project, "trust/bad.py", """\
            import requests
        """)
        result = check_trust_purity(f)
        assert result["pass"] is False

    def test_non_trust_skipped(self, tmp_project):
        f = _write_file(tmp_project, "utils/helper.py", """\
            import os
            import logging
        """)
        result = check_trust_purity(f)
        assert result["pass"] is True
        assert "skipped" in result.get("note", "")

    def test_hashlib_allowed(self, tmp_project):
        f = _write_file(tmp_project, "trust/signature.py", """\
            import hashlib
            import hmac
            import json
        """)
        result = check_trust_purity(f)
        assert result["pass"] is True


# ── check_protocol_conformance ─────────────────────────────────────────


class TestCheckProtocolConformance:
    def test_conforming_adapter(self, tmp_project):
        _write_file(tmp_project, "trust/protocols.py", """\
            from typing import Protocol, runtime_checkable

            @runtime_checkable
            class IdentityProvider(Protocol):
                def get_caller_identity(self): ...
                def resolve_identity(self, identifier: str): ...
                def verify_identity(self, identity): ...
        """)
        adapter = _write_file(tmp_project, "utils/local_provider.py", """\
            class LocalIdentityProvider:
                def get_caller_identity(self):
                    return {}
                def resolve_identity(self, identifier: str):
                    return {}
                def verify_identity(self, identity):
                    return {}
        """)
        result = check_protocol_conformance(adapter, "IdentityProvider")
        assert result["pass"] is True
        assert result["missing_methods"] == []

    def test_missing_method(self, tmp_project):
        _write_file(tmp_project, "trust/protocols.py", """\
            from typing import Protocol, runtime_checkable

            @runtime_checkable
            class IdentityProvider(Protocol):
                def get_caller_identity(self): ...
                def resolve_identity(self, identifier: str): ...
                def verify_identity(self, identity): ...
        """)
        adapter = _write_file(tmp_project, "utils/incomplete.py", """\
            class IncompleteProvider:
                def get_caller_identity(self):
                    return {}
        """)
        result = check_protocol_conformance(adapter, "IdentityProvider")
        assert result["pass"] is False
        assert "resolve_identity" in result["missing_methods"]
        assert "verify_identity" in result["missing_methods"]

    def test_protocol_not_found(self, tmp_project):
        _write_file(tmp_project, "trust/protocols.py", """\
            from typing import Protocol

            class SomeOtherProtocol(Protocol):
                def method(self): ...
        """)
        adapter = _write_file(tmp_project, "utils/adapter.py", """\
            class Adapter:
                pass
        """)
        result = check_protocol_conformance(adapter, "NonExistentProtocol")
        assert result["pass"] is False
        assert any("not found" in v["description"] for v in result["violations"])

    def test_no_protocols_file(self, tmp_path):
        adapter = tmp_path / "standalone.py"
        adapter.write_text("class Foo:\n    pass\n")
        result = check_protocol_conformance(adapter, "SomeProtocol")
        assert result["pass"] is False
        assert any("Could not locate" in v["description"] for v in result["violations"])


# ── detect_anti_patterns ───────────────────────────────────────────────


class TestDetectAntiPatterns:
    def test_clean_agents_file(self, tmp_project):
        f = _write_file(tmp_project, "agents/reviewer.py", """\
            from utils.prompt_service import PromptService
            from trust.models import AgentFacts

            class Reviewer:
                pass
        """)
        result = detect_anti_patterns(f)
        assert result["pass"] is True
        assert result["violations"] == []

    def test_ap2_vertical_to_vertical(self, tmp_project):
        f = _write_file(tmp_project, "agents/smart_writer.py", """\
            from agents.reviewer_panel import get_panel_review
        """)
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP2" for v in result["violations"])

    def test_ap3_hardcoded_prompt(self, tmp_project):
        f = _write_file(tmp_project, "agents/writer.py", """\
            topic = "math"
            system_prompt = f"You are a {topic} expert"
        """)
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP3" for v in result["violations"])

    def test_ap5_direct_io_in_agents(self, tmp_project):
        f = _write_file(tmp_project, "agents/writer.py", """\
            class Writer:
                def save(self):
                    with open("output.txt", "w") as fh:
                        fh.write("data")
        """)
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP5" for v in result["violations"])

    def test_ap6_basemodel_in_utils(self, tmp_project):
        f = _write_file(tmp_project, "utils/shared_types.py", """\
            from pydantic import BaseModel

            class MyModel(BaseModel):
                name: str
        """)
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP6" for v in result["violations"])

    def test_ap6_not_triggered_in_trust(self, tmp_project):
        f = _write_file(tmp_project, "trust/models.py", """\
            from pydantic import BaseModel

            class AgentFacts(BaseModel):
                agent_id: str
        """)
        result = detect_anti_patterns(f)
        assert result["pass"] is True

    def test_clean_utils_file(self, tmp_project):
        f = _write_file(tmp_project, "utils/helper.py", """\
            import ast
            from pathlib import Path

            def parse(filepath):
                return ast.parse(Path(filepath).read_text())
        """)
        result = detect_anti_patterns(f)
        assert result["pass"] is True

    def test_syntax_error_file(self, tmp_project):
        f = _write_file(tmp_project, "agents/bad.py", "def broken(:\n")
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert result["violations"][0]["rule"] == "AP.PARSE"
