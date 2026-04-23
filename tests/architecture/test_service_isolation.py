"""Architecture: Horizontal-to-horizontal isolation (AGENTS.md AP-2).

Verifies that the three S1 horizontal services do not import from each
other or from any other peer in `services/*` (except `services.base_config`,
which is the only shared infra hook). Uses AST parsing -- no imports are
executed.

Source of truth for these rules:
- docs/plan/services/TRACE_SERVICE_PLAN.md §3.4
- docs/plan/services/LONG_TERM_MEMORY_PLAN.md §3.4
- docs/plan/services/AUTHORIZATION_SERVICE_PLAN.md §4.4
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.code_analysis import parse_imports

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent

ALLOWED_SERVICES_SUBMODULES: set[str] = {
    "services.base_config",
    # The S1 services may have local subpackages (e.g.
    # services.memory_backends for long_term_memory). Adapter and
    # backend re-exports are allowed; peer-service imports are not.
    "services.memory_backends",
    "services.memory_backends.in_memory",
}


def _service_imports(rel_path: str) -> list[tuple[str, int]]:
    """Return (module, line) pairs that look like `services.*` imports."""
    parsed = parse_imports(AGENT_ROOT / rel_path)
    assert parsed["pass"], f"Could not parse {rel_path}: {parsed}"
    out: list[tuple[str, int]] = []
    for imp in parsed["imports"]:
        module = imp["module"]
        if module == "services" or module.startswith("services."):
            out.append((module, imp["line"]))
    return out


def _assert_no_peer_service_imports(rel_path: str) -> None:
    own_module = rel_path.replace("/", ".").removesuffix(".py")
    violations: list[str] = []
    for module, line in _service_imports(rel_path):
        if module == own_module or module.startswith(own_module + "."):
            continue
        if module in ALLOWED_SERVICES_SUBMODULES:
            continue
        violations.append(f"line {line}: imports {module}")
    assert violations == [], (
        f"{rel_path} violates AP-2 by importing from peer services:\n  "
        + "\n  ".join(violations)
    )


class TestS1ServiceIsolation:
    def test_trace_service_does_not_import_other_services(self):
        _assert_no_peer_service_imports("services/trace_service.py")

    def test_long_term_memory_does_not_import_other_services(self):
        _assert_no_peer_service_imports("services/long_term_memory.py")

    def test_authorization_service_does_not_import_other_services(self):
        _assert_no_peer_service_imports("services/authorization_service.py")

    def test_authorization_service_does_not_import_registry(self):
        """Explicit AP-2 enforcement (plan §4.4): the authorization
        service must never import `AgentFactsRegistry`. The orchestrator
        passes verified facts in as a parameter."""
        parsed = parse_imports(AGENT_ROOT / "services" / "authorization_service.py")
        violations = [
            (imp["module"], imp["line"])
            for imp in parsed["imports"]
            if "agent_facts_registry" in imp["module"]
        ]
        assert violations == [], (
            "services/authorization_service.py must not import "
            "agent_facts_registry (AP-2):\n  "
            + "\n  ".join(f"line {ln}: imports {mod}" for mod, ln in violations)
        )
