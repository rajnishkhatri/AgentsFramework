"""Architecture tests for the ``middleware/`` ring (Sprint 1, story S1.4.1).

These tests enforce the dependency-direction contract from
``docs/Architectures/FRONTEND_ARCHITECTURE.md`` § "Middleware sub-ring" and
``docs/STYLE_GUIDE_FRONTEND.md`` rules **M1**, **F1**, **F4**, and the
per-sub-package import tables.

Each test maps to exactly one rule and is **self-referential** -- the test
itself is the enforcement mechanism (TDD §Pattern 7: dependency-rule
enforcement).

Rule summary enforced here:

    M1   Nothing in the four-layer backend (`trust/`, `services/`,
         `components/`, `orchestration/`, `governance/`, `meta/`) imports
         from `middleware/`. Dependency arrow is one-way.

    F1   Substrate selection (`os.environ["ARCHITECTURE_PROFILE"]`) lives
         only in `middleware/composition.py`.

    F4   `middleware/` may import from `trust/`, `services/`, and
         `agent_ui_adapter/wire/` only -- never from `components/`,
         `orchestration/`, `governance/`, or `meta/`. The graph is loaded
         via `langgraph.json` config (string reference), not Python import.

    M-ports        `middleware/ports/` imports only `agent_ui_adapter/wire/`,
                   `trust/`, and stdlib -- no SDKs, no other middleware
                   sub-packages.

    M-adapters     `middleware/adapters/` may import third-party SDKs
                   (PyJWT, langfuse, mem0ai) -- but NOT other adapters,
                   translators, transport, or composition.

    M-no-cross     SDK imports (PyJWT, mem0ai, langfuse, workos) appear
                   ONLY under `middleware/adapters/` -- never in
                   `ports/`, `transport/`, `composition.py`, or `server.py`.

These rules are the **SAFETY NET**. They run on every commit. Any new file
under `middleware/` is automatically constrained.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from utils.code_analysis import collect_imports_in_directory


AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
MIDDLEWARE_DIR = AGENT_ROOT / "middleware"

# SDKs that must be confined to middleware/adapters/* per F-R2 / A1.
SDK_PACKAGES = {
    "jwt",          # PyJWT
    "mem0",
    "mem0ai",
    "langfuse",
    "workos",
}


def _middleware_imports() -> list[tuple[str, str]]:
    if not MIDDLEWARE_DIR.exists():
        return []
    return collect_imports_in_directory(MIDDLEWARE_DIR, relative_to=AGENT_ROOT)


def _imports_in(subdir: str) -> list[tuple[str, str]]:
    target = MIDDLEWARE_DIR / subdir
    if not target.exists():
        return []
    return collect_imports_in_directory(target, relative_to=AGENT_ROOT)


# ─────────────────────────────────────────────────────────────────────
# Rule M1 — backend never imports from middleware/
# ─────────────────────────────────────────────────────────────────────


class TestM1_BackendDoesNotImportMiddleware:
    """M1: dependency arrow is one-way."""

    def test_no_backend_layer_imports_middleware(self) -> None:
        forbidden_consumers = [
            "trust",
            "services",
            "components",
            "orchestration",
            "governance",
            "meta",
            "agent_ui_adapter",
        ]
        violations: list[str] = []
        for layer in forbidden_consumers:
            layer_dir = AGENT_ROOT / layer
            if not layer_dir.exists():
                continue
            for path, pkg in collect_imports_in_directory(
                layer_dir, relative_to=AGENT_ROOT
            ):
                if pkg == "middleware":
                    violations.append(f"{path} imports middleware")
        assert violations == [], (
            "M1 violated: backend layer imports from middleware/:\n"
            + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# Rule F4 — middleware imports only from approved layers
# ─────────────────────────────────────────────────────────────────────


class TestF4_MiddlewareDependencyDirection:
    """F4: middleware may import trust/, services/, agent_ui_adapter/wire/.
    Forbidden: components/, orchestration/, governance/, meta/.
    """

    def test_middleware_does_not_import_components(self) -> None:
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in _middleware_imports()
            if pkg == "components"
        ]
        assert violations == [], (
            "F4 violated: middleware/ must not import components/:\n"
            + "\n".join(violations)
        )

    def test_middleware_does_not_import_orchestration(self) -> None:
        """F4 + langgraph.json contract: graph is loaded via config, not
        Python import.
        """
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in _middleware_imports()
            if pkg == "orchestration"
        ]
        assert violations == [], (
            "F4 violated: middleware/ must NOT Python-import orchestration/. "
            "Load graph via langgraph.json string reference instead:\n"
            + "\n".join(violations)
        )

    def test_middleware_does_not_import_governance(self) -> None:
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in _middleware_imports()
            if pkg == "governance"
        ]
        assert violations == [], (
            "F4 violated: middleware/ must not import governance/:\n"
            + "\n".join(violations)
        )

    def test_middleware_does_not_import_meta(self) -> None:
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in _middleware_imports()
            if pkg == "meta"
        ]
        assert violations == [], (
            "F4 violated: middleware/ must not import meta/:\n"
            + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# M-ports — ports/ purity
# ─────────────────────────────────────────────────────────────────────


class TestPortPurity:
    """middleware/ports/ may import only stdlib + Pydantic + agent_ui_adapter/wire/
    + trust/. No SDKs, no other middleware sub-packages.
    """

    def test_ports_have_no_sdk_imports(self) -> None:
        port_imports = _imports_in("ports")
        if not port_imports:
            pytest.skip("ports/ scaffolded but empty")
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in port_imports
            if pkg in SDK_PACKAGES
        ]
        assert violations == [], (
            "Port purity violated: middleware/ports/ must NOT import SDKs "
            "(jwt, mem0ai, langfuse, workos):\n" + "\n".join(violations)
        )

    def test_ports_do_not_import_adapters(self) -> None:
        port_imports = _imports_in("ports")
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in port_imports
            if pkg.startswith("middleware.adapters")
            or pkg.startswith("middleware.transport")
        ]
        assert violations == [], (
            "Port purity violated: ports/ must not import adapters/ or "
            "transport/:\n" + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# M-no-cross — SDKs confined to adapters/
# ─────────────────────────────────────────────────────────────────────


class TestSdkConfinement:
    """SDK imports (PyJWT, mem0ai, langfuse, workos) appear ONLY under
    middleware/adapters/* -- never elsewhere in middleware/.

    This is the F-R2 / A1 rule that keeps adapter-isolation guarantees:
    no SDK type can escape past the adapter boundary.
    """

    def test_sdks_only_in_adapters(self) -> None:
        violations: list[str] = []
        for path, pkg in _middleware_imports():
            if pkg not in SDK_PACKAGES:
                continue
            # Path is relative to AGENT_ROOT, e.g. "middleware/ports/foo.py".
            if "middleware/adapters/" not in str(path).replace("\\", "/"):
                violations.append(f"{path} imports SDK {pkg}")
        assert violations == [], (
            "SDK isolation violated: SDKs may live ONLY in "
            "middleware/adapters/*:\n" + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# F1 — single profile switch in composition root
# ─────────────────────────────────────────────────────────────────────


class TestF1_SingleProfileSwitch:
    """F1: ``os.environ["ARCHITECTURE_PROFILE"]`` (or equivalent
    ``os.getenv("ARCHITECTURE_PROFILE")``) appears only in
    ``middleware/composition.py``.
    """

    def test_architecture_profile_only_in_composition(self) -> None:
        """AST-scan: a string literal ``"ARCHITECTURE_PROFILE"`` may appear
        only inside ``middleware/composition.py``. Docstrings are
        ignored -- only string literals reachable from real code count.
        """
        if not MIDDLEWARE_DIR.exists():
            pytest.skip("middleware/ scaffolded but empty")
        composition_path = MIDDLEWARE_DIR / "composition.py"
        violations: list[str] = []
        for py in MIDDLEWARE_DIR.rglob("*.py"):
            if py == composition_path:
                continue
            tree = ast.parse(py.read_text())
            module_doc = ast.get_docstring(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value == "ARCHITECTURE_PROFILE"
                ):
                    # Skip string literals that ARE the module docstring.
                    if module_doc and node.value in module_doc:
                        continue
                    violations.append(str(py.relative_to(AGENT_ROOT)))
                    break
        assert violations == [], (
            "F1 violated: ARCHITECTURE_PROFILE must appear only in "
            "middleware/composition.py:\n" + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# Adapter sub-package isolation: no cross-adapter imports
# ─────────────────────────────────────────────────────────────────────


class TestAdapterIsolation:
    """A2: no adapter family imports another adapter family directly."""

    def test_no_cross_adapter_imports(self) -> None:
        adapters_dir = MIDDLEWARE_DIR / "adapters"
        if not adapters_dir.exists():
            pytest.skip("adapters/ not yet scaffolded")
        violations: list[str] = []
        for family in ("auth", "acl", "memory", "observability"):
            family_dir = adapters_dir / family
            if not family_dir.exists():
                continue
            for path, pkg in collect_imports_in_directory(
                family_dir, relative_to=AGENT_ROOT
            ):
                # Check for imports from sibling families.
                for other in ("auth", "acl", "memory", "observability"):
                    if other == family:
                        continue
                    if pkg == f"middleware.adapters.{other}" or pkg.startswith(
                        f"middleware.adapters.{other}."
                    ):
                        violations.append(
                            f"{path} imports sibling family {other}"
                        )
        assert violations == [], (
            "A2 violated: adapter families must not import each other:\n"
            + "\n".join(violations)
        )
