"""Cross-cutting: Dependency rule enforcement (Pattern 7).

Verifies that no module imports from a layer above it:
- trust/ must not import from utils/ or agents/
- utils/ must not import from agents/

Also enforces structural-conformance checks from the Trust Foundation
plan (planned files exist, enums/signature modules present, boto3
declared as a dependency).

Runs via AST parsing -- no imports are executed.

STORY-411: import-extraction logic is delegated to
``utils.code_analysis.collect_imports_in_directory`` and the layer rules
themselves live in ``utils.code_analysis.FORBIDDEN_IMPORTS`` /
``FRAMEWORK_FORBIDDEN`` so the architecture tests, the CodeReviewer
agent, and any future tooling share a single source of truth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.code_analysis import (
    FORBIDDEN_IMPORTS as AUTHORITATIVE_FORBIDDEN_IMPORTS,
    FRAMEWORK_FORBIDDEN as AUTHORITATIVE_FRAMEWORK_FORBIDDEN,
    check_dependency_rules,
    collect_imports_in_directory,
    parse_imports,
)

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent

# Local re-exports preserved for downstream tooling that may have imported
# them from this module historically. They MUST NOT be redefined here.
FORBIDDEN_IMPORTS = AUTHORITATIVE_FORBIDDEN_IMPORTS
FRAMEWORK_FORBIDDEN = AUTHORITATIVE_FRAMEWORK_FORBIDDEN


def _collect_imported_packages(source_dir: Path) -> list[tuple[str, str]]:
    """Compatibility wrapper around the shared utility helper."""
    return collect_imports_in_directory(source_dir, relative_to=AGENT_ROOT)


class TestDependencyRules:
    def test_trust_does_not_import_utils(self):
        violations = []
        for filepath, pkg in _collect_imported_packages(AGENT_ROOT / "trust"):
            if pkg in {"utils", "agents", "governance"}:
                violations.append(f"{filepath} imports {pkg}")
        assert violations == [], (
            "trust/ must not import from upper layers:\n" + "\n".join(violations)
        )

    def test_trust_does_not_import_agents(self):
        violations = []
        for filepath, pkg in _collect_imported_packages(AGENT_ROOT / "trust"):
            if pkg == "agents":
                violations.append(f"{filepath} imports agents")
        assert violations == [], "trust/ must not import from agents/:\n" + "\n".join(
            violations
        )

    def test_utils_does_not_import_agents(self):
        violations = []
        for filepath, pkg in _collect_imported_packages(AGENT_ROOT / "utils"):
            if pkg in {"agents", "governance", "orchestration"}:
                violations.append(f"{filepath} imports {pkg}")
        assert violations == [], (
            "utils/ must not import from upper layers:\n" + "\n".join(violations)
        )

    def test_components_no_framework_imports(self):
        """components/ must not import langgraph or langchain (framework-agnostic)."""
        forbidden = {"langgraph", "langchain", "langchain_core", "langchain_community"}
        comp_dir = AGENT_ROOT / "components"
        if not comp_dir.exists():
            pytest.skip("components/ not yet created")
        violations = []
        for filepath, pkg in _collect_imported_packages(comp_dir):
            if pkg in forbidden:
                violations.append(f"{filepath} imports {pkg}")
        assert violations == [], (
            "components/ must not import framework packages:\n" + "\n".join(violations)
        )

    def test_components_does_not_import_orchestration(self):
        """components/ must not import from orchestration/."""
        comp_dir = AGENT_ROOT / "components"
        if not comp_dir.exists():
            pytest.skip("components/ not yet created")
        violations = []
        for filepath, pkg in _collect_imported_packages(comp_dir):
            if pkg == "orchestration":
                violations.append(f"{filepath} imports orchestration")
        assert violations == [], (
            "components/ must not import orchestration:\n" + "\n".join(violations)
        )

    def test_services_no_framework_imports_except_llm_config(self):
        """services/ must not import langgraph/langchain except llm_config.py."""
        forbidden = {"langgraph", "langchain_core", "langchain_community"}
        svc_dir = AGENT_ROOT / "services"
        if not svc_dir.exists():
            pytest.skip("services/ not yet created")
        violations = []
        for filepath, pkg in _collect_imported_packages(svc_dir):
            if pkg in forbidden and "llm_config" not in filepath:
                violations.append(f"{filepath} imports {pkg}")
        assert violations == [], (
            "services/ (except llm_config.py) must not import framework packages:\n"
            + "\n".join(violations)
        )

    def test_services_does_not_import_components(self):
        """services/ must not import from components/ (prevents reverse coupling)."""
        svc_dir = AGENT_ROOT / "services"
        if not svc_dir.exists():
            pytest.skip("services/ not yet created")
        violations = []
        for filepath, pkg in _collect_imported_packages(svc_dir):
            if pkg == "components":
                violations.append(f"{filepath} imports components")
        assert violations == [], (
            "services/ must not import from components/:\n" + "\n".join(violations)
        )

    def test_llm_providers_is_langchain_free(self):
        """The direct-call extension (services/llm_providers/) is the
        LangChain-FREE client layer — the boundary shim that touches langchain
        lives in services/llm_config.py, NOT here. A regression that pulls
        langchain into the provider client breaks the "pure client" contract."""
        providers_dir = AGENT_ROOT / "services" / "llm_providers"
        if not providers_dir.exists():
            pytest.skip("services/llm_providers/ not yet created")
        forbidden = {
            "langchain",
            "langchain_core",
            "langchain_community",
            "langchain_litellm",
            "langgraph",
            "litellm",
        }
        violations = []
        for filepath, pkg in _collect_imported_packages(providers_dir):
            if pkg in forbidden:
                violations.append(f"{filepath} imports {pkg}")
        assert violations == [], (
            "services/llm_providers/ must stay LangChain/LiteLLM-free "
            "(direct REST client only):\n" + "\n".join(violations)
        )

    def test_llm_providers_does_not_import_upper_layers(self):
        """services/llm_providers/ (Horizontal) imports only downward —
        trust/ + stdlib + httpx, never components/orchestration/agents/governance."""
        providers_dir = AGENT_ROOT / "services" / "llm_providers"
        if not providers_dir.exists():
            pytest.skip("services/llm_providers/ not yet created")
        violations = []
        for filepath, pkg in _collect_imported_packages(providers_dir):
            if pkg in {
                "components",
                "orchestration",
                "agents",
                "governance",
                "middleware",
            }:
                violations.append(f"{filepath} imports {pkg}")
        assert violations == [], (
            "services/llm_providers/ must not import from upper layers:\n"
            + "\n".join(violations)
        )

    def test_meta_does_not_import_orchestration(self):
        """meta/ must not import from orchestration/ (meta is horizontal, not above orchestration)."""
        meta_dir = AGENT_ROOT / "meta"
        if not meta_dir.exists():
            pytest.skip("meta/ not yet created")
        violations = []
        for filepath, pkg in _collect_imported_packages(meta_dir):
            if pkg == "orchestration":
                violations.append(f"{filepath} imports orchestration")
        assert violations == [], (
            "meta/ must not import from orchestration/:\n" + "\n".join(violations)
        )


# ═══════════════════════════════════════════════════════════════════════
# T3 (Phase 4) — supervisor_plan.py layer purity (Pattern 7).
#
# Step 3 of t3_implementation_and_validation.plan.md §2. Written BEFORE the
# module exists: these go RED on module-absent (the correct first failure /
# the binding-is-the-test). The decompose-or-decline component is pure
# components/ (LP-1/LP-2, AGENTS inv. 1/3/5/6): it must import no langgraph,
# no orchestration, no AgentState, and no SIBLING components/* module
# (no V→V coupling). The async dispatcher edit (Step 5b) must keep
# delegation_dispatcher.py free of langgraph/orchestration too.
#
# Reuses the shared AST scanner (collect_imports_in_directory / parse_imports)
# — no new scanner, per plan Step 3.
# ═══════════════════════════════════════════════════════════════════════


SUPERVISOR_PLAN = AGENT_ROOT / "components" / "supervisor_plan.py"
SUPERVISOR_PLAN_TEST = AGENT_ROOT / "tests" / "components" / "test_supervisor_plan.py"


def _imports_of(py_file: Path) -> list[dict]:
    """Per-import records (module / names / top_package) for one file."""
    parsed = parse_imports(py_file)
    assert parsed["pass"], f"{py_file} failed to parse: {parsed.get('error')}"
    return parsed["imports"]


class TestSupervisorPlanLayerPurity:
    """T3 component (components/supervisor_plan.py) is framework-agnostic."""

    def test_module_exists(self):
        """RED until Step 4 lands the module — this binding IS the spec."""
        assert SUPERVISOR_PLAN.exists(), (
            "components/supervisor_plan.py must exist (T3 Step 4)"
        )

    def test_no_langgraph_or_orchestration_import(self):
        """LP-1: no langgraph, no orchestration, no AgentState (by package)."""
        if not SUPERVISOR_PLAN.exists():
            pytest.skip("components/supervisor_plan.py not yet created (RED)")
        forbidden = {
            "langgraph",
            "langchain",
            "langchain_core",
            "langchain_community",
            "orchestration",
        }
        violations = [
            f"line {imp['line']}: imports {imp['top_package']}"
            for imp in _imports_of(SUPERVISOR_PLAN)
            if imp["top_package"] in forbidden
        ]
        assert violations == [], (
            "supervisor_plan.py must import no framework/orchestration:\n"
            + "\n".join(violations)
        )

    def test_no_agentstate_symbol(self):
        """LP-1: AgentState must not be imported by name from anywhere."""
        if not SUPERVISOR_PLAN.exists():
            pytest.skip("components/supervisor_plan.py not yet created (RED)")
        violations = [
            f"line {imp['line']}: imports AgentState from {imp['module']}"
            for imp in _imports_of(SUPERVISOR_PLAN)
            if "AgentState" in imp.get("names", [])
        ]
        assert violations == [], (
            "supervisor_plan.py must not import AgentState:\n" + "\n".join(violations)
        )

    def test_no_vertical_to_vertical_import(self):
        """LP-2 / inv. 5: no V→V — no import of any OTHER components/* module."""
        if not SUPERVISOR_PLAN.exists():
            pytest.skip("components/supervisor_plan.py not yet created (RED)")
        violations = [
            f"line {imp['line']}: imports sibling {imp['module']}"
            for imp in _imports_of(SUPERVISOR_PLAN)
            if imp["top_package"] == "components"
        ]
        assert violations == [], (
            "supervisor_plan.py must not import sibling components/* modules "
            "(no vertical-to-vertical coupling):\n" + "\n".join(violations)
        )

    def test_dispatcher_stays_framework_clean(self):
        """LP-1 preserved: the Step-5b async edit keeps the dispatcher clean."""
        dispatcher = AGENT_ROOT / "services" / "tools" / "delegation_dispatcher.py"
        assert dispatcher.exists(), "delegation_dispatcher.py must exist"
        forbidden = {
            "langgraph",
            "langchain_core",
            "langchain_community",
            "orchestration",
        }
        violations = [
            f"line {imp['line']}: imports {imp['top_package']}"
            for imp in _imports_of(dispatcher)
            if imp["top_package"] in forbidden
        ]
        assert violations == [], (
            "delegation_dispatcher.py must stay framework/orchestration-clean:\n"
            + "\n".join(violations)
        )

    def test_component_test_does_not_import_orchestration(self):
        """AP7: run P7 against the test tree too — the component test is pure."""
        if not SUPERVISOR_PLAN_TEST.exists():
            pytest.skip(
                "tests/components/test_supervisor_plan.py not yet created (RED)"
            )
        forbidden = {"langgraph", "orchestration"}
        violations = [
            f"line {imp['line']}: imports {imp['top_package']}"
            for imp in _imports_of(SUPERVISOR_PLAN_TEST)
            if imp["top_package"] in forbidden
        ]
        assert violations == [], (
            "test_supervisor_plan.py must not import orchestration/langgraph:\n"
            + "\n".join(violations)
        )


# ═══════════════════════════════════════════════════════════════════════
# Plan structural conformance (migrated from Branch 1/Branch 5 of the
# legacy test_plan_hypothesis_validation.py suite)
# ═══════════════════════════════════════════════════════════════════════


PLANNED_FILES = [
    "trust/cloud_identity.py",
    "trust/protocols.py",
    "trust/__init__.py",
    "utils/cloud_providers/__init__.py",
    "utils/cloud_providers/aws_identity.py",
    "utils/cloud_providers/aws_policy.py",
    "utils/cloud_providers/aws_credentials.py",
    "utils/cloud_providers/local_provider.py",
    "meta/__init__.py",
    "meta/judge.py",
    "meta/run_eval.py",
    "meta/analysis.py",
    "meta/drift.py",
    "services/tools/sandbox.py",
]


class TestPlannedFilesExist:
    """H1: Every file specified in the plan's file-by-file section exists."""

    @pytest.mark.parametrize("rel_path", PLANNED_FILES)
    def test_planned_file_exists(self, rel_path):
        full = AGENT_ROOT / rel_path
        assert full.exists(), (
            f"Plan requires {rel_path} but file does not exist at {full}"
        )

    def test_enums_module_exists(self):
        """H5.2a: trust/enums.py shown in the architecture diagram exists."""
        assert (AGENT_ROOT / "trust" / "enums.py").exists(), (
            "trust/enums.py should exist (GAP-4 resolved)"
        )

    def test_signature_module_exists(self):
        """H5.2b: trust/signature.py shown in the architecture diagram exists."""
        assert (AGENT_ROOT / "trust" / "signature.py").exists(), (
            "trust/signature.py should exist (GAP-4 resolved)"
        )

    def test_undocumented_additions_present(self):
        """Modules NOT in the plan but required by implementation exist."""
        assert (AGENT_ROOT / "trust" / "exceptions.py").exists(), (
            "trust/exceptions.py is required by the exception hierarchy"
        )
        assert (AGENT_ROOT / "utils" / "cloud_providers" / "config.py").exists(), (
            "utils/cloud_providers/config.py is required by TrustProviderSettings"
        )


# ═══════════════════════════════════════════════════════════════════════
# STORY-411: Shared-utility parity
#
# Confirms that ``utils.code_analysis.check_dependency_rules`` (consumed by
# meta/code_reviewer.py) yields the same set of violations the architecture
# test harness derives from ``collect_imports_in_directory`` plus the
# authoritative ``FORBIDDEN_IMPORTS`` table. Eliminates the prior risk of
# the test harness and the CodeReviewer drifting apart.
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "layer_dir",
    sorted(set(AUTHORITATIVE_FORBIDDEN_IMPORTS.keys())),
)
class TestSharedUtilityParity:
    def test_check_dependency_rules_matches_harness_scan(self, layer_dir):
        """The CodeReviewer path and the harness path agree, file-for-file."""
        source_dir = AGENT_ROOT / layer_dir
        if not source_dir.exists():
            pytest.skip(f"{layer_dir}/ not yet created")

        forbidden = AUTHORITATIVE_FORBIDDEN_IMPORTS[layer_dir]
        harness_violations: set[tuple[str, str, str]] = set()
        for py_file in source_dir.rglob("*.py"):
            for path, pkg in collect_imports_in_directory(
                py_file.parent, relative_to=AGENT_ROOT
            ):
                if path != str(py_file.relative_to(AGENT_ROOT)):
                    continue
                if pkg in forbidden:
                    harness_violations.add((path, layer_dir, pkg))

        utility_violations: set[tuple[str, str, str]] = set()
        for py_file in source_dir.rglob("*.py"):
            result = check_dependency_rules(py_file)
            if result["pass"]:
                continue
            rel = str(py_file.relative_to(AGENT_ROOT))
            for v in result.get("violations", []):
                rule = v.get("rule", "")
                # Rule format: "DEP.<layer>_cannot_import_<pkg>"
                if not rule.startswith("DEP."):
                    continue
                _, _, suffix = rule.partition("DEP.")
                marker = f"{layer_dir}_cannot_import_"
                if not suffix.startswith(marker):
                    continue
                pkg = suffix[len(marker) :]
                utility_violations.add((rel, layer_dir, pkg))

        assert harness_violations == utility_violations, (
            f"Harness vs. CodeReviewer mismatch in {layer_dir}/.\n"
            f"Only in harness: {harness_violations - utility_violations}\n"
            f"Only in utility: {utility_violations - harness_violations}"
        )


class TestDeclaredDependencies:
    """H5.3: boto3 is declared as a dependency in pyproject.toml."""

    def test_boto3_in_pyproject(self):
        pyproject_path = AGENT_ROOT / "pyproject.toml"
        assert pyproject_path.exists(), f"pyproject.toml must exist at {pyproject_path}"
        content = pyproject_path.read_text()
        assert "boto3" in content, (
            "boto3 must be listed in pyproject.toml (aws optional-deps)"
        )
