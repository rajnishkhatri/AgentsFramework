"""Architecture tests for the inner ``StructuredReasoning/*`` layers.

Mirrors the rules in ``tests/architecture/test_dependency_rules.py`` but
scoped to the inner four-layer mirror under ``StructuredReasoning/``.

Allowed import directions (inner layers only -- outer layers may always
import from each other within their own table):

    StructuredReasoning/trust/         -> stdlib + pydantic + outer trust/
    StructuredReasoning/services/      -> the above + outer services/
    StructuredReasoning/components/    -> the above + outer components/
    StructuredReasoning/orchestration/ -> everything below + langgraph + langchain_core

Forbidden upward imports are enforced here (e.g., trust must not import
services; services must not import components; components must not import
orchestration). Framework imports (``langgraph``/``langchain``) are
forbidden everywhere except ``orchestration/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.code_analysis import collect_imports_in_directory

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
SR_ROOT = AGENT_ROOT / "StructuredReasoning"

# Top-level packages whose imports we treat as layer markers. Any import
# whose top package is in this set and matches a forbidden cell signals a
# layer violation. Sibling outer layers (e.g. outer ``services``) are NOT
# in this set when allowed, but ARE in this set when forbidden upward.
FRAMEWORK_PACKAGES = frozenset({
    "langgraph", "langchain", "langchain_core", "langchain_community",
    "langchain_litellm",
})


def _scan(layer: str) -> list[tuple[str, str]]:
    layer_dir = SR_ROOT / layer
    if not layer_dir.exists():
        pytest.skip(f"StructuredReasoning/{layer}/ not yet created")
    return collect_imports_in_directory(layer_dir, relative_to=AGENT_ROOT)


class TestStructuredReasoningTrustPurity:
    """Inner trust/ may only import stdlib + pydantic + outer trust + sibling SR trust."""

    def test_inner_trust_does_not_import_outer_services(self):
        violations = [
            (path, pkg) for path, pkg in _scan("trust")
            if pkg == "services"
        ]
        assert violations == [], (
            "StructuredReasoning/trust/ must not import outer services/:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )

    def test_inner_trust_does_not_import_outer_components(self):
        violations = [
            (path, pkg) for path, pkg in _scan("trust")
            if pkg == "components"
        ]
        assert violations == [], (
            "StructuredReasoning/trust/ must not import outer components/:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )

    def test_inner_trust_does_not_import_orchestration(self):
        violations = [
            (path, pkg) for path, pkg in _scan("trust")
            if pkg == "orchestration"
        ]
        assert violations == [], (
            "StructuredReasoning/trust/ must not import orchestration/:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )

    def test_inner_trust_no_framework_imports(self):
        violations = [
            (path, pkg) for path, pkg in _scan("trust")
            if pkg in FRAMEWORK_PACKAGES
        ]
        assert violations == [], (
            "StructuredReasoning/trust/ must not import langgraph/langchain:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )

    def test_inner_trust_does_not_import_meta(self):
        violations = [
            (path, pkg) for path, pkg in _scan("trust")
            if pkg == "meta"
        ]
        assert violations == [], (
            "StructuredReasoning/trust/ must not import meta/:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )


class TestStructuredReasoningServicesIsolation:
    """Inner services/ may import outer trust + outer services + sibling SR trust.

    Forbidden: outer components/, outer orchestration/, framework packages.
    """

    def test_inner_services_does_not_import_components(self):
        violations = [
            (path, pkg) for path, pkg in _scan("services")
            if pkg == "components"
        ]
        assert violations == [], (
            "StructuredReasoning/services/ must not import outer components/:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )

    def test_inner_services_does_not_import_orchestration(self):
        violations = [
            (path, pkg) for path, pkg in _scan("services")
            if pkg == "orchestration"
        ]
        assert violations == [], (
            "StructuredReasoning/services/ must not import orchestration/:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )

    def test_inner_services_no_framework_imports(self):
        violations = [
            (path, pkg) for path, pkg in _scan("services")
            if pkg in FRAMEWORK_PACKAGES
        ]
        assert violations == [], (
            "StructuredReasoning/services/ must not import langgraph/langchain:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )


class TestStructuredReasoningComponentsIsolation:
    """Inner components/ may import outer trust + outer services + outer components + sibling SR layers.

    Forbidden: outer orchestration/, framework packages.
    """

    def test_inner_components_does_not_import_orchestration(self):
        violations = [
            (path, pkg) for path, pkg in _scan("components")
            if pkg == "orchestration"
        ]
        assert violations == [], (
            "StructuredReasoning/components/ must not import orchestration/:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )

    def test_inner_components_no_framework_imports(self):
        violations = [
            (path, pkg) for path, pkg in _scan("components")
            if pkg in FRAMEWORK_PACKAGES
        ]
        assert violations == [], (
            "StructuredReasoning/components/ must not import langgraph/langchain:\n"
            + "\n".join(f"{p} imports {pkg}" for p, pkg in violations)
        )


class TestStructuredReasoningOrchestrationOnlyFrameworkConsumer:
    """Only the inner orchestration layer is allowed to import langgraph/langchain.

    Verified positively: at least one orchestration file imports langgraph
    (the ``pyramid_loop`` build entry point). The negative case for the
    other layers is covered by the tests above.
    """

    def test_orchestration_imports_langgraph(self):
        pairs = _scan("orchestration")
        framework_imports = {pkg for _path, pkg in pairs if pkg in FRAMEWORK_PACKAGES}
        assert "langgraph" in framework_imports, (
            "StructuredReasoning/orchestration/ should import langgraph "
            f"(found: {sorted(framework_imports)})"
        )
