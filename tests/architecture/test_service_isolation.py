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


# ─────────────────────────────────────────────────────────────────────
# Phase 2 (replace-mem0-pgvector) — PgVectorMemoryBackend isolation
# ─────────────────────────────────────────────────────────────────────
#
# Per docs/plans/replace_mem0_pgvector.plan.md §Architecture & TDD compliance:
#   • The new backend lives in services/memory_backends/ — same slot as
#     in_memory/sqlite/mem0; AP-2 forbids it from importing peer services
#     OR sibling backends (the in-memory backend, the mem0 backend, etc.).
#   • The backend MAY import middleware/ports/ (a Protocol port is
#     framework-agnostic, by plan §Architecture & TDD compliance table).
#   • Dependency direction (rule 1): no orchestration/, components/,
#     middleware/adapters/* imports. The composition root constructs the
#     backend and injects the EmbeddingClient.
#   • psycopg lives in services/ only under this file (+ the BFF thread
#     store in agent_ui_adapter/adapters/runtime/postgres_saver.py, which
#     is not a service — covered by the existing M1 layering test).


class TestPgVectorBackendIsolation:
    """Phase 2 layering guarantees for services/memory_backends/pgvector.py."""

    PG = "services/memory_backends/pgvector.py"

    # The backend's allowed dependency set. Anything else from these layers
    # would be a violation; explicit denylist makes the failure message
    # readable.
    _FORBIDDEN_TOP_LEVEL_PREFIXES = (
        "orchestration",
        "components",
        "governance",
        "meta",
        "trust",
    )

    def test_does_not_import_forbidden_layers(self) -> None:
        path = AGENT_ROOT / self.PG
        if not path.exists():
            pytest.skip("pgvector backend not yet scaffolded")
        parsed = parse_imports(path)
        violations: list[str] = []
        for imp in parsed["imports"]:
            module = imp["module"]
            top = module.split(".")[0]
            if top in self._FORBIDDEN_TOP_LEVEL_PREFIXES:
                violations.append(f"line {imp['line']}: imports {module}")
        assert violations == [], (
            f"{self.PG} violates dependency rules — must not import "
            "orchestration/components/governance/meta/trust:\n  "
            + "\n  ".join(violations)
        )

    def test_does_not_import_middleware_adapters(self) -> None:
        """Plan §Architecture: middleware/ports/ is permitted (ports are
        framework-agnostic Protocols); middleware/adapters/ is NOT — the
        composition root constructs adapters and injects them.
        """
        path = AGENT_ROOT / self.PG
        if not path.exists():
            pytest.skip("pgvector backend not yet scaffolded")
        parsed = parse_imports(path)
        violations = [
            f"line {imp['line']}: imports {imp['module']}"
            for imp in parsed["imports"]
            if imp["module"].startswith("middleware.adapters")
        ]
        assert violations == [], (
            f"{self.PG} must not import middleware/adapters/* directly — "
            "the composition root injects adapters via the EmbeddingClient port:\n  "
            + "\n  ".join(violations)
        )

    def test_does_not_import_sibling_backends_or_peer_services(self) -> None:
        """AP-2 explicit: the backend may import its OWN package
        (``services.memory_backends.pgvector``), ``services.base_config``,
        and ``services.long_term_memory`` (which owns the Protocol types
        it implements). Nothing else from ``services/*``.
        """
        path = AGENT_ROOT / self.PG
        if not path.exists():
            pytest.skip("pgvector backend not yet scaffolded")
        allowed = {
            "services.base_config",
            "services.long_term_memory",
            "services.memory_backends.pgvector",
        }
        parsed = parse_imports(path)
        violations: list[str] = []
        for imp in parsed["imports"]:
            module = imp["module"]
            if not (module == "services" or module.startswith("services.")):
                continue
            if module in allowed:
                continue
            violations.append(f"line {imp['line']}: imports {module}")
        assert violations == [], (
            f"{self.PG} violates AP-2 by importing peer services:\n  "
            + "\n  ".join(violations)
        )


class TestPsycopgConfinement:
    """Phase 2: ``psycopg`` may appear in services/ only under the
    pgvector backend. Other potential psycopg consumers in the tree
    (the BFF thread store) live under agent_ui_adapter/ — covered by
    its own layer test."""

    def test_psycopg_in_services_only_under_pgvector(self) -> None:
        services_dir = AGENT_ROOT / "services"
        if not services_dir.exists():
            pytest.skip("services/ not yet scaffolded")
        violations: list[str] = []
        for py in services_dir.rglob("*.py"):
            if "__pycache__" in str(py):
                continue
            parsed = parse_imports(py)
            if not parsed.get("pass"):
                continue
            for imp in parsed["imports"]:
                top = imp["module"].split(".")[0]
                if top in ("psycopg", "psycopg_pool"):
                    rel = py.relative_to(AGENT_ROOT)
                    if str(rel) != "services/memory_backends/pgvector.py":
                        violations.append(
                            f"{rel}:{imp['line']} imports {imp['module']}"
                        )
        assert violations == [], (
            "psycopg confinement violated — in services/ it may live "
            "only under memory_backends/pgvector.py:\n  "
            + "\n  ".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# Phase 6 (replace-mem0-pgvector) — recall invariant validator isolation
# ─────────────────────────────────────────────────────────────────────
#
# Per docs/plans/replace_mem0_pgvector.plan.md §Phase 6 + the
# agentsframework-eval-probe skill's Phase 4 layer rules:
#   • The L1 deterministic check lives in services/governance/ as a pure
#     function — stdlib + pydantic + the MemoryRecord type it scores against.
#   • No framework imports (langgraph/langchain/openai/litellm/psycopg/…).
#   • No imports from orchestration/, components/, meta/, trust/, or
#     middleware/adapters/. The composition root wires the validator into
#     the recall seam at react_loop.py.
#   • A judge, if Phase 7 ever earns one, would live in components/ — NOT
#     in this file.


class TestMemoryRecallValidatorIsolation:
    """Phase 6 layering guarantees for
    services/governance/memory_recall_validator.py."""

    MV = "services/governance/memory_recall_validator.py"

    _FORBIDDEN_TOP_LEVEL_PREFIXES = (
        "orchestration",
        "components",
        "meta",
        "trust",
    )

    _FORBIDDEN_FRAMEWORK_PREFIXES = (
        "langgraph",
        "langchain",
        "openai",
        "litellm",
        "psycopg",
        "psycopg_pool",
        "sqlalchemy",
    )

    def test_does_not_import_forbidden_layers(self) -> None:
        path = AGENT_ROOT / self.MV
        parsed = parse_imports(path)
        violations: list[str] = []
        for imp in parsed["imports"]:
            top = imp["module"].split(".")[0]
            if top in self._FORBIDDEN_TOP_LEVEL_PREFIXES:
                violations.append(f"line {imp['line']}: imports {imp['module']}")
        assert violations == [], (
            f"{self.MV} must not import "
            "orchestration/components/meta/trust:\n  "
            + "\n  ".join(violations)
        )

    def test_does_not_import_frameworks(self) -> None:
        path = AGENT_ROOT / self.MV
        parsed = parse_imports(path)
        violations = [
            f"line {imp['line']}: imports {imp['module']}"
            for imp in parsed["imports"]
            if imp["module"].split(".")[0] in self._FORBIDDEN_FRAMEWORK_PREFIXES
        ]
        assert violations == [], (
            f"{self.MV} must stay framework-free — pure function over the "
            "MemoryRecord type only:\n  " + "\n  ".join(violations)
        )

    def test_does_not_import_middleware(self) -> None:
        path = AGENT_ROOT / self.MV
        parsed = parse_imports(path)
        violations = [
            f"line {imp['line']}: imports {imp['module']}"
            for imp in parsed["imports"]
            if imp["module"].startswith("middleware")
        ]
        assert violations == [], (
            f"{self.MV} must not import middleware/* — the composition "
            "root wires the validator into the recall seam:\n  "
            + "\n  ".join(violations)
        )

    def test_only_imports_long_term_memory_from_peer_services(self) -> None:
        """The validator owns the MemoryRecord type via long_term_memory
        (same precedent as guardrail_validator importing GuardRail). It
        must NOT import other peer services (eval_capture, eval_telemetry,
        any sibling governance module).
        """
        path = AGENT_ROOT / self.MV
        parsed = parse_imports(path)
        allowed = {
            "services.long_term_memory",
            "services.governance.memory_recall_validator",
        }
        violations: list[str] = []
        for imp in parsed["imports"]:
            module = imp["module"]
            if not (module == "services" or module.startswith("services.")):
                continue
            if module in allowed:
                continue
            violations.append(f"line {imp['line']}: imports {module}")
        assert violations == [], (
            f"{self.MV} violates AP-2 by importing peer services beyond "
            "long_term_memory:\n  " + "\n  ".join(violations)
        )
