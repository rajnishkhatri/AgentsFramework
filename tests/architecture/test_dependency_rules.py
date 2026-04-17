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
        assert violations == [], (
            "trust/ must not import from agents/:\n" + "\n".join(violations)
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
                pkg = suffix[len(marker):]
                utility_violations.add((rel, layer_dir, pkg))

        assert harness_violations == utility_violations, (
            f"Harness vs. CodeReviewer mismatch in {layer_dir}/.\n"
            f"Only in harness: {harness_violations - utility_violations}\n"
            f"Only in utility: {utility_violations - harness_violations}"
        )


class TestDeclaredDependencies:
    """H5.3: boto3 is listed as a dependency per Step 9 of the plan."""

    def test_boto3_in_requirements(self):
        req_path = AGENT_ROOT / "requirements.txt"
        assert req_path.exists(), (
            f"requirements.txt must exist at {req_path}"
        )
        content = req_path.read_text()
        assert "boto3" in content, (
            "boto3 must be listed in requirements.txt per Step 9 of the plan"
        )
