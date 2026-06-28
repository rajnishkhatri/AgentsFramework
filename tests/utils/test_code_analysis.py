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
    detect_adr1_missing,
    detect_anti_patterns,
    detect_failure_path_ratio,
    detect_mock_abuse,
    detect_test_weakening,
    parse_imports,
)


# ── Helpers ────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project skeleton for testing."""
    for d in (
        "trust",
        "utils",
        "agents",
        "governance",
        "services",
        "components",
        "orchestration",
    ):
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
        f = _write_file(
            tmp_project,
            "trust/models.py",
            """\
            from pydantic import BaseModel
            from trust.enums import IdentityStatus
        """,
        )
        result = parse_imports(f)
        assert result["pass"] is True
        modules = [i["module"] for i in result["imports"]]
        assert "pydantic" in modules
        assert "trust.enums" in modules

    def test_bare_import(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/helper.py",
            """\
            import ast
            import pathlib
        """,
        )
        result = parse_imports(f)
        assert result["pass"] is True
        modules = [i["module"] for i in result["imports"]]
        assert "ast" in modules
        assert "pathlib" in modules

    def test_top_package_extracted(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/helper.py",
            """\
            from trust.models import AgentFacts
        """,
        )
        result = parse_imports(f)
        assert result["imports"][0]["top_package"] == "trust"

    def test_line_numbers(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/helper.py",
            """\
            import os
            from pathlib import Path
        """,
        )
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
        f = _write_file(
            tmp_project,
            "trust/models.py",
            """\
            from pydantic import BaseModel
            from trust.enums import IdentityStatus
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is True
        assert result["violations"] == []

    def test_trust_imports_utils_fails(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/bad.py",
            """\
            from utils.helper import some_function
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert len(result["violations"]) == 1
        assert "utils" in result["violations"][0]["description"]

    def test_trust_imports_agents_fails(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/bad.py",
            """\
            from agents.writer import Writer
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("agents" in v["description"] for v in result["violations"])

    def test_utils_clean(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/helper.py",
            """\
            import ast
            from trust.models import AgentFacts
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_utils_imports_agents_fails(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/bad.py",
            """\
            from agents.writer import Writer
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("agents" in v["description"] for v in result["violations"])

    def test_services_imports_trust_ok(self, tmp_project):
        f = _write_file(
            tmp_project,
            "services/llm_config.py",
            """\
            from trust.models import AgentFacts
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_services_imports_components_fails(self, tmp_project):
        f = _write_file(
            tmp_project,
            "services/bad.py",
            """\
            from components.schemas import EvalRecord
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("components" in v["description"] for v in result["violations"])

    def test_services_imports_orchestration_fails(self, tmp_project):
        f = _write_file(
            tmp_project,
            "services/bad.py",
            """\
            from orchestration.state import AgentState
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any(
            "orchestration" in v["description"].lower() for v in result["violations"]
        )

    def test_components_imports_services_ok(self, tmp_project):
        f = _write_file(
            tmp_project,
            "components/router.py",
            """\
            from services.base_config import AgentConfig
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_components_imports_orchestration_fails(self, tmp_project):
        f = _write_file(
            tmp_project,
            "components/bad.py",
            """\
            from orchestration.react_loop import build_graph
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any(
            "orchestration" in v["description"].lower() for v in result["violations"]
        )

    def test_trust_imports_services_fails(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/bad.py",
            """\
            from services.llm_config import LLMService
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert any("services" in v["description"].lower() for v in result["violations"])

    def test_agents_file_not_checked(self, tmp_project):
        f = _write_file(
            tmp_project,
            "agents/reviewer.py",
            """\
            from utils.helper import func
            from trust.models import AgentFacts
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is True

    def test_multiple_violations(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/bad.py",
            """\
            from utils.helper import func
            from agents.writer import Writer
        """,
        )
        result = check_dependency_rules(f)
        assert result["pass"] is False
        assert len(result["violations"]) == 2


# ── check_trust_purity ─────────────────────────────────────────────────


class TestCheckTrustPurity:
    def test_pure_trust_file(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/models.py",
            """\
            from __future__ import annotations
            from datetime import datetime
            from typing import Any
            from pydantic import BaseModel
        """,
        )
        result = check_trust_purity(f)
        assert result["pass"] is True

    def test_impure_logging(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/bad.py",
            """\
            import logging
            from pydantic import BaseModel
        """,
        )
        result = check_trust_purity(f)
        assert result["pass"] is False
        assert any("logging" in v["description"] for v in result["violations"])

    def test_impure_os(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/bad.py",
            """\
            import os
        """,
        )
        result = check_trust_purity(f)
        assert result["pass"] is False

    def test_impure_requests(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/bad.py",
            """\
            import requests
        """,
        )
        result = check_trust_purity(f)
        assert result["pass"] is False

    def test_non_trust_skipped(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/helper.py",
            """\
            import os
            import logging
        """,
        )
        result = check_trust_purity(f)
        assert result["pass"] is True
        assert "skipped" in result.get("note", "")

    def test_hashlib_allowed(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/signature.py",
            """\
            import hashlib
            import hmac
            import json
        """,
        )
        result = check_trust_purity(f)
        assert result["pass"] is True


# ── check_protocol_conformance ─────────────────────────────────────────


class TestCheckProtocolConformance:
    def test_conforming_adapter(self, tmp_project):
        _write_file(
            tmp_project,
            "trust/protocols.py",
            """\
            from typing import Protocol, runtime_checkable

            @runtime_checkable
            class IdentityProvider(Protocol):
                def get_caller_identity(self): ...
                def resolve_identity(self, identifier: str): ...
                def verify_identity(self, identity): ...
        """,
        )
        adapter = _write_file(
            tmp_project,
            "utils/local_provider.py",
            """\
            class LocalIdentityProvider:
                def get_caller_identity(self):
                    return {}
                def resolve_identity(self, identifier: str):
                    return {}
                def verify_identity(self, identity):
                    return {}
        """,
        )
        result = check_protocol_conformance(adapter, "IdentityProvider")
        assert result["pass"] is True
        assert result["missing_methods"] == []

    def test_missing_method(self, tmp_project):
        _write_file(
            tmp_project,
            "trust/protocols.py",
            """\
            from typing import Protocol, runtime_checkable

            @runtime_checkable
            class IdentityProvider(Protocol):
                def get_caller_identity(self): ...
                def resolve_identity(self, identifier: str): ...
                def verify_identity(self, identity): ...
        """,
        )
        adapter = _write_file(
            tmp_project,
            "utils/incomplete.py",
            """\
            class IncompleteProvider:
                def get_caller_identity(self):
                    return {}
        """,
        )
        result = check_protocol_conformance(adapter, "IdentityProvider")
        assert result["pass"] is False
        assert "resolve_identity" in result["missing_methods"]
        assert "verify_identity" in result["missing_methods"]

    def test_protocol_not_found(self, tmp_project):
        _write_file(
            tmp_project,
            "trust/protocols.py",
            """\
            from typing import Protocol

            class SomeOtherProtocol(Protocol):
                def method(self): ...
        """,
        )
        adapter = _write_file(
            tmp_project,
            "utils/adapter.py",
            """\
            class Adapter:
                pass
        """,
        )
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
        f = _write_file(
            tmp_project,
            "agents/reviewer.py",
            """\
            from utils.prompt_service import PromptService
            from trust.models import AgentFacts

            class Reviewer:
                pass
        """,
        )
        result = detect_anti_patterns(f)
        assert result["pass"] is True
        assert result["violations"] == []

    def test_ap2_vertical_to_vertical(self, tmp_project):
        f = _write_file(
            tmp_project,
            "agents/smart_writer.py",
            """\
            from agents.reviewer_panel import get_panel_review
        """,
        )
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP2" for v in result["violations"])

    def test_ap3_hardcoded_prompt(self, tmp_project):
        f = _write_file(
            tmp_project,
            "agents/writer.py",
            """\
            topic = "math"
            system_prompt = f"You are a {topic} expert"
        """,
        )
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP3" for v in result["violations"])

    def test_ap5_direct_io_in_agents(self, tmp_project):
        f = _write_file(
            tmp_project,
            "agents/writer.py",
            """\
            class Writer:
                def save(self):
                    with open("output.txt", "w") as fh:
                        fh.write("data")
        """,
        )
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP5" for v in result["violations"])

    def test_ap6_basemodel_in_utils(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/shared_types.py",
            """\
            from pydantic import BaseModel

            class MyModel(BaseModel):
                name: str
        """,
        )
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert any(v["rule"] == "AP6" for v in result["violations"])

    def test_ap6_not_triggered_in_trust(self, tmp_project):
        f = _write_file(
            tmp_project,
            "trust/models.py",
            """\
            from pydantic import BaseModel

            class AgentFacts(BaseModel):
                agent_id: str
        """,
        )
        result = detect_anti_patterns(f)
        assert result["pass"] is True

    def test_clean_utils_file(self, tmp_project):
        f = _write_file(
            tmp_project,
            "utils/helper.py",
            """\
            import ast
            from pathlib import Path

            def parse(filepath):
                return ast.parse(Path(filepath).read_text())
        """,
        )
        result = detect_anti_patterns(f)
        assert result["pass"] is True

    def test_syntax_error_file(self, tmp_project):
        f = _write_file(tmp_project, "agents/bad.py", "def broken(:\n")
        result = detect_anti_patterns(f)
        assert result["pass"] is False
        assert result["violations"][0]["rule"] == "AP.PARSE"


# ── G8: test-weakening detector ────────────────────────────────────────


class TestDetectTestWeakening:
    """Pure detector for the G8 (test-mass-rewrite) gate. Failure paths first."""

    def test_removed_test_is_flagged(self):
        old = textwrap.dedent("""\
            def test_a():
                assert True

            def test_b():
                assert 1 == 1
        """)
        new = textwrap.dedent("""\
            def test_a():
                assert True
        """)
        result = detect_test_weakening(old, new)
        assert result["pass"] is False
        rules = {v["rule"] for v in result["violations"]}
        assert "G8.TEST_REMOVED" in rules
        assert any("test_b" in v["description"] for v in result["violations"])

    def test_newly_added_skip_is_flagged(self):
        old = textwrap.dedent("""\
            def test_a():
                assert True
        """)
        new = textwrap.dedent("""\
            import pytest

            @pytest.mark.skip
            def test_a():
                assert True
        """)
        result = detect_test_weakening(old, new)
        assert result["pass"] is False
        assert {v["rule"] for v in result["violations"]} == {"G8.TEST_SKIPPED"}

    def test_newly_added_xfail_is_flagged(self):
        old = "def test_a():\n    assert True\n"
        new = textwrap.dedent("""\
            import pytest

            @pytest.mark.xfail(reason="broken")
            def test_a():
                assert True
        """)
        result = detect_test_weakening(old, new)
        assert result["pass"] is False
        assert "test_a" in result["violations"][0]["description"]

    def test_skipif_on_method_is_flagged(self):
        old = textwrap.dedent("""\
            class TestThing:
                def test_x(self):
                    assert True
        """)
        new = textwrap.dedent("""\
            import pytest

            class TestThing:
                @pytest.mark.skipif(True, reason="meh")
                def test_x(self):
                    assert True
        """)
        result = detect_test_weakening(old, new)
        assert result["pass"] is False
        assert "test_x" in result["violations"][0]["description"]

    def test_unchanged_suite_passes(self):
        src = textwrap.dedent("""\
            def test_a():
                assert True

            def test_b():
                assert 2 == 2
        """)
        assert detect_test_weakening(src, src)["pass"] is True

    def test_added_test_passes(self):
        old = "def test_a():\n    assert True\n"
        new = "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n"
        assert detect_test_weakening(old, new)["pass"] is True

    def test_preexisting_skip_not_flagged(self):
        # A skip that was already there in the base must not fire (only NEW skips do).
        src = textwrap.dedent("""\
            import pytest

            @pytest.mark.skip(reason="legacy")
            def test_a():
                assert True
        """)
        assert detect_test_weakening(src, src)["pass"] is True

    def test_justified_skip_is_allowed(self):
        old = "def test_a():\n    assert True\n"
        for reason in ("G8-OK env not available", "see ADR-0007", "flaky-tracked: #42"):
            new = textwrap.dedent(f"""\
                import pytest

                @pytest.mark.skip(reason="{reason}")
                def test_a():
                    assert True
            """)
            result = detect_test_weakening(old, new)
            assert result["pass"] is True, f"justification {reason!r} should pass"

    def test_live_llm_marker_is_allowed(self):
        # The repo bans live LLM in CI; marking a test live_llm is a sanctioned guard.
        old = "def test_a():\n    assert True\n"
        new = textwrap.dedent("""\
            import pytest

            @pytest.mark.skipif(True, reason="live_llm only")
            def test_a():
                assert True
        """)
        assert detect_test_weakening(old, new)["pass"] is True

    def test_unparseable_new_is_conservative_fail(self):
        result = detect_test_weakening("def test_a():\n    pass\n", "def broken(:\n")
        assert result["pass"] is False
        assert result["violations"][0]["rule"] == "G8.PARSE_NEW"

    def test_removal_waived_by_named_comment(self):
        # A rename declared with a '# G8-OK: <removed test>' comment is allowed.
        old = "def test_old_name():\n    assert True\n"
        new = textwrap.dedent("""\
            # G8-OK: test_old_name renamed to test_new_name (same assertion)
            def test_new_name():
                assert True
        """)
        assert detect_test_weakening(old, new)["pass"] is True

    def test_removal_waiver_must_name_the_test(self):
        # A generic '# G8-OK' that does NOT name the removed test must not waive it.
        old = "def test_old_name():\n    assert True\n"
        new = textwrap.dedent("""\
            # G8-OK: unrelated waiver
            def test_new_name():
                assert True
        """)
        result = detect_test_weakening(old, new)
        assert result["pass"] is False
        assert result["violations"][0]["rule"] == "G8.TEST_REMOVED"


# ── ADR.1 file-list scan (WI-5) ─────────────────────────────────────────


class TestDetectAdr1Missing:
    """The deterministic half of the ADR ratchet: an ⚠️ Ask-first trigger with
    no new docs/adr/ file is a violation. Pure file-list, no git."""

    def test_benign_diff_passes(self):
        result = detect_adr1_missing(["README.md", "docs/plan/foo.md"])
        assert result["pass"] is True
        assert result["violations"] == []
        assert result["triggers"] == []

    def test_empty_diff_passes(self):
        assert detect_adr1_missing([])["pass"] is True

    def test_pyproject_trigger_without_adr_flagged(self):
        result = detect_adr1_missing(["pyproject.toml"])
        assert result["pass"] is False
        v = result["violations"][0]
        assert v["rule"] == "ADR.1"
        assert "pyproject.toml" in v["triggers"]

    def test_trust_models_trigger_flagged(self):
        result = detect_adr1_missing(["trust/models.py", "README.md"])
        assert result["pass"] is False
        assert "trust/models.py" in result["violations"][0]["triggers"]

    def test_react_loop_trigger_flagged(self):
        result = detect_adr1_missing(["orchestration/react_loop.py"])
        assert result["pass"] is False
        assert result["triggers"] == ["orchestration/react_loop.py"]

    def test_multiple_triggers_listed(self):
        result = detect_adr1_missing(["pyproject.toml", "trust/models.py"])
        assert result["pass"] is False
        triggers = result["violations"][0]["triggers"]
        assert "pyproject.toml" in triggers
        assert "trust/models.py" in triggers

    def test_adr_filed_in_changed_is_relief(self):
        result = detect_adr1_missing(["pyproject.toml", "docs/adr/0042-new-dep.md"])
        assert result["pass"] is True
        assert result["adr_filed"] is True

    def test_adr_filed_in_added_is_relief(self):
        # A new ADR is an *added* file; callers may pass it only via added_files.
        result = detect_adr1_missing(
            ["pyproject.toml"], added_files=["docs/adr/0043-trust-type.md"]
        )
        assert result["pass"] is True
        assert result["adr_filed"] is True

    def test_non_adr_docs_path_is_not_relief(self):
        # docs/plan/foo.md is not an ADR — no relief.
        result = detect_adr1_missing(["pyproject.toml", "docs/plan/foo.md"])
        assert result["pass"] is False

    def test_new_horizontal_service_flagged(self):
        result = detect_adr1_missing(
            ["services/newsvc/__init__.py", "services/newsvc/foo.py"],
            added_files=["services/newsvc/__init__.py"],
        )
        assert result["pass"] is False
        assert any(
            t.startswith("services/newsvc/__init__.py")
            for t in result["violations"][0]["triggers"]
        )

    def test_new_service_requires_added_files(self):
        # Without added_files, a services/ path is not auto-treated as a new
        # service (it could be an edit to an existing service).
        result = detect_adr1_missing(["services/existing/foo.py"])
        assert result["pass"] is True

    def test_new_service_with_adr_filed_passes(self):
        result = detect_adr1_missing(
            ["services/newsvc/__init__.py", "docs/adr/0044-new-service.md"],
            added_files=["services/newsvc/__init__.py", "docs/adr/0044-new-service.md"],
        )
        assert result["pass"] is True

    def test_backslash_paths_normalized(self):
        # Windows-style paths should be normalized to posix before matching.
        result = detect_adr1_missing(["trust\\models.py"])
        assert result["pass"] is False
        assert "trust/models.py" in result["violations"][0]["triggers"]

    def test_description_names_the_triggers(self):
        result = detect_adr1_missing(["pyproject.toml"])
        desc = result["violations"][0]["description"]
        assert "pyproject.toml" in desc
        assert "docs/adr/" in desc


# ── TAP-2 mock-abuse detector ───────────────────────────────────────────


class TestDetectMockAbuse:
    """TAP-2 (mock addiction): >3 mocks in one test is a warning."""

    def test_clean_test_passes(self):
        src = textwrap.dedent("""\
            def test_happy():
                assert 1 == 1
        """)
        assert detect_mock_abuse(src)["pass"] is True

    def test_three_mocks_at_threshold_passes(self):
        # >3 is the trigger; exactly 3 is allowed.
        src = textwrap.dedent("""\
            from unittest.mock import patch
            @patch("a.b")
            @patch("c.d")
            @patch("e.f")
            def test_three(mock1, mock2, mock3):
                pass
        """)
        assert detect_mock_abuse(src)["pass"] is True

    def test_four_mocks_flagged(self):
        src = textwrap.dedent("""\
            from unittest.mock import patch, MagicMock
            @patch("a.b")
            @patch("c.d")
            @patch("e.f")
            def test_four(mock1, mock2, mock3):
                m = MagicMock()
                pass
        """)
        result = detect_mock_abuse(src)
        assert result["pass"] is False
        v = result["violations"][0]
        assert v["rule"] == "TAP-2"
        assert v["test"] == "test_four"
        assert v["mock_count"] == 4

    def test_patch_object_and_multiple_count(self):
        src = textwrap.dedent("""\
            from unittest.mock import patch, MagicMock
            @patch.object(a, "b")
            @patch.multiple(c, d="x")
            @patch("e.f")
            @patch("g.h")
            def test_overloaded():
                pass
        """)
        result = detect_mock_abuse(src)
        assert result["pass"] is False
        assert result["violations"][0]["mock_count"] == 4

    def test_mock_constructions_in_body_count(self):
        src = textwrap.dedent("""\
            from unittest.mock import MagicMock, AsyncMock
            def test_mocks_in_body():
                a = MagicMock()
                b = MagicMock()
                c = AsyncMock()
                d = MagicMock()
                assert a and b and c and d
        """)
        result = detect_mock_abuse(src)
        assert result["pass"] is False
        assert result["violations"][0]["mock_count"] == 4

    def test_dotted_mock_path_counted(self):
        # mock.MagicMock / unittest.mock.patch forms count too.
        src = textwrap.dedent("""\
            import unittest.mock
            def test_dotted():
                a = unittest.mock.MagicMock()
                b = unittest.mock.MagicMock()
                c = unittest.mock.MagicMock()
                d = unittest.mock.patch("x.y").start()
                assert a
        """)
        result = detect_mock_abuse(src)
        assert result["pass"] is False

    def test_non_test_functions_not_counted(self):
        src = textwrap.dedent("""\
            from unittest.mock import MagicMock
            def helper():
                a = MagicMock(); b = MagicMock(); c = MagicMock(); d = MagicMock()
                return a
            def test_uses_helper():
                helper()
        """)
        # The mocks are in a non-test helper — test_uses_helper itself has 0.
        assert detect_mock_abuse(src)["pass"] is True

    def test_non_mock_names_not_counted(self):
        # A variable literally named `mock` must not be counted; only
        # patch*/MagicMock/etc. calls and decorators are anchors.
        src = textwrap.dedent("""\
            def test_naming():
                mock = "not a mock"
                fake = object()
                assert mock and fake
        """)
        assert detect_mock_abuse(src)["pass"] is True

    def test_unparseable_is_conservative_fail(self):
        result = detect_mock_abuse("def broken(:\n")
        assert result["pass"] is False
        assert result["violations"][0]["rule"] == "TAP-2.PARSE"

    def test_custom_threshold(self):
        src = textwrap.dedent("""\
            from unittest.mock import patch
            @patch("a.b")
            @patch("c.d")
            def test_two():
                pass
        """)
        # 2 mocks; default threshold 3 passes; threshold 1 flags.
        assert detect_mock_abuse(src)["pass"] is True
        assert detect_mock_abuse(src, threshold=1)["pass"] is False


# ── TAP-4 failure-path ratio detector ───────────────────────────────────


class TestDetectFailurePathRatio:
    """TAP-4 (failure-paths-first): a suite with too low a failure-test ratio
    is a warning. Generous heuristic — biased toward passing."""

    def test_all_failure_tests_pass(self):
        src = textwrap.dedent("""\
            import pytest
            def test_rejects_bad(): assert True
            def test_invalid_input(): assert True
            def test_raises_on_missing():
                with pytest.raises(ValueError):
                    raise ValueError()
            def test_denied(): assert True
        """)
        result = detect_failure_path_ratio(src)
        assert result["pass"] is True
        assert result["total"] == 4
        assert result["failure_tests"] == 4

    def test_all_happy_tests_flagged(self):
        src = textwrap.dedent("""\
            def test_happy_one(): assert True
            def test_happy_two(): assert True
            def test_happy_three(): assert True
            def test_happy_four(): assert True
            def test_happy_five(): assert True
        """)
        result = detect_failure_path_ratio(src)
        assert result["pass"] is False
        v = result["violations"][0]
        assert v["rule"] == "TAP-4"
        assert result["ratio"] == 0.0

    def test_below_min_tests_passes(self):
        # 3 happy tests — below min_tests=4, not enough signal to flag.
        src = textwrap.dedent("""\
            def test_happy_one(): assert True
            def test_happy_two(): assert True
            def test_happy_three(): assert True
        """)
        assert detect_failure_path_ratio(src)["pass"] is True

    def test_pytest_raises_counts_as_failure(self):
        src = textwrap.dedent("""\
            import pytest
            def test_a():
                with pytest.raises(KeyError):
                    raise KeyError()
            def test_b(): assert True
            def test_c(): assert True
            def test_d(): assert True
        """)
        result = detect_failure_path_ratio(src)
        assert result["pass"] is True  # 1/4 = 25% == min_ratio (not below)
        assert result["failure_tests"] == 1

    def test_assert_not_counts_as_failure(self):
        src = textwrap.dedent("""\
            def test_returns_none():
                assert not True
            def test_happy_two(): assert True
            def test_happy_three(): assert True
            def test_happy_four(): assert True
        """)
        result = detect_failure_path_ratio(src)
        assert result["failure_tests"] == 1
        assert result["pass"] is True  # 1/4 == min_ratio

    def test_assert_is_none_counts_as_failure(self):
        src = textwrap.dedent("""\
            def test_none_result():
                x = None
                assert x is None
            def test_happy_two(): assert True
            def test_happy_three(): assert True
            def test_happy_four(): assert True
            def test_happy_five(): assert True
        """)
        result = detect_failure_path_ratio(src)
        assert result["failure_tests"] == 1

    def test_rejection_name_counts_as_failure(self):
        src = textwrap.dedent("""\
            def test_invalid_input_rejected(): assert True
            def test_happy_two(): assert True
            def test_happy_three(): assert True
            def test_happy_four(): assert True
        """)
        result = detect_failure_path_ratio(src)
        assert result["failure_tests"] == 1
        assert result["pass"] is True  # 1/4 == min_ratio

    def test_custom_threshold(self):
        src = textwrap.dedent("""\
            def test_rejected(): assert True
            def test_happy_two(): assert True
            def test_happy_three(): assert True
            def test_happy_four(): assert True
        """)
        # 1/4 = 25%; default min_ratio 0.25 passes; stricter 0.5 flags.
        assert detect_failure_path_ratio(src)["pass"] is True
        assert detect_failure_path_ratio(src, min_ratio=0.5)["pass"] is False

    def test_unparseable_is_conservative_fail(self):
        result = detect_failure_path_ratio("def broken(:\n")
        assert result["pass"] is False
        assert result["violations"][0]["rule"] == "TAP-4.PARSE"

    def test_empty_module_passes(self):
        result = detect_failure_path_ratio("# no tests here\n")
        assert result["pass"] is True
        assert result["total"] == 0
        assert result["ratio"] == 0.0

