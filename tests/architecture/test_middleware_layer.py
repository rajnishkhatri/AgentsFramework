"""Architecture tests for the ``middleware/`` ring (Sprint 1, story S1.4.1).

These tests enforce the dependency-direction contract from
``docs/Architectures/FRONTEND_ARCHITECTURE.md`` § "Middleware sub-ring" and
``docs/style-guides/STYLE_GUIDE_FRONTEND.md`` rules **M1**, **F1**, **F4**, and the
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

from utils.code_analysis import collect_imports_in_directory, parse_imports


AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
MIDDLEWARE_DIR = AGENT_ROOT / "middleware"

# SDKs that must be confined to middleware/adapters/* per F-R2 / A1.
SDK_PACKAGES = {
    "jwt",  # PyJWT
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
    """M1: dependency arrow is one-way.

    The general rule (top-level ``import middleware`` from any backend
    layer) stays banned. A narrow exception is documented for
    ``middleware.ports.*`` imports from ``services/``: ports are
    framework-agnostic Protocols (no SDK, no concrete adapter), and the
    hexagonal layering says "services may consume ports" (per
    ``docs/plans/replace_mem0_pgvector.plan.md`` §Architecture & TDD
    compliance — ``services/memory_backends/pgvector.py`` consumes
    ``middleware.ports.embedding_client.EmbeddingClient``).

    The intent of M1 — keeping SDK/adapter coupling out of the backend —
    is still enforced by ``TestPortPurity`` (ports must be stdlib-only)
    and ``TestSdkConfinement`` (SDKs may live only under
    ``middleware/adapters/``).
    """

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
        # Sanctioned narrow exception (plan §Architecture & TDD compliance):
        # backend services may import middleware.ports.* — ports are pure
        # Protocols and the hexagonal contract says services consume them.
        violations: list[str] = []
        for layer in forbidden_consumers:
            layer_dir = AGENT_ROOT / layer
            if not layer_dir.exists():
                continue
            for py in layer_dir.rglob("*.py"):
                if "__pycache__" in str(py):
                    continue
                parsed = parse_imports(py)
                if not parsed.get("pass"):
                    continue
                for imp in parsed["imports"]:
                    module = imp["module"]
                    if not (module == "middleware" or module.startswith("middleware.")):
                        continue
                    # Narrow exception: services may consume middleware.ports.*
                    if layer == "services" and module.startswith("middleware.ports"):
                        continue
                    rel = py.relative_to(AGENT_ROOT)
                    violations.append(f"{rel}:{imp['line']} imports {module}")
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
            "F4 violated: middleware/ must not import meta/:\n" + "\n".join(violations)
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
            f"{path} imports {pkg}" for path, pkg in port_imports if pkg in SDK_PACKAGES
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
                        violations.append(f"{path} imports sibling family {other}")
        assert violations == [], (
            "A2 violated: adapter families must not import each other:\n"
            + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# C1/I-10 — app_prod must not import langfuse SDK
# ─────────────────────────────────────────────────────────────────────


class TestAppProdSdkIsolation:
    """app_prod.py, __main__.py, and telemetry_bridge.py must not import the
    langfuse SDK.

    The SDK is confined to middleware/adapters/observability/. Production
    and dev entry points use only the port Protocol (TelemetryExporter).
    """

    def test_dev_main_does_not_import_langfuse(self) -> None:
        """Phase 4: __main__.py imports LangfuseCloudExporter (adapter), not
        the langfuse SDK directly."""
        main_file = MIDDLEWARE_DIR / "__main__.py"
        if not main_file.exists():
            pytest.skip("__main__.py not yet scaffolded")
        imports = collect_imports_in_directory(MIDDLEWARE_DIR, relative_to=AGENT_ROOT)
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "__main__" in str(path) and pkg == "langfuse"
        ]
        assert violations == [], (
            "C1/I-10 violated: __main__.py must NOT import langfuse SDK "
            "(use LangfuseCloudExporter adapter or port instead):\n"
            + "\n".join(violations)
        )

    def test_app_prod_does_not_import_langfuse(self) -> None:
        app_prod = MIDDLEWARE_DIR / "app_prod.py"
        if not app_prod.exists():
            pytest.skip("app_prod.py not yet scaffolded")
        imports = collect_imports_in_directory(MIDDLEWARE_DIR, relative_to=AGENT_ROOT)
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "app_prod" in str(path) and pkg == "langfuse"
        ]
        assert violations == [], (
            "C1/I-10 violated: app_prod.py must NOT import langfuse SDK "
            "(use port TelemetryExporter instead):\n" + "\n".join(violations)
        )

    def test_telemetry_bridge_does_not_import_langfuse(self) -> None:
        bridge = MIDDLEWARE_DIR / "telemetry_bridge.py"
        if not bridge.exists():
            pytest.skip("telemetry_bridge.py not yet created")
        imports = collect_imports_in_directory(MIDDLEWARE_DIR, relative_to=AGENT_ROOT)
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "telemetry_bridge" in str(path) and pkg == "langfuse"
        ]
        assert violations == [], (
            "C1/I-10 violated: telemetry_bridge.py must NOT import langfuse "
            "SDK (use port TelemetryExporter instead):\n" + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# Bridge import allowlist — only stdlib + wire + port
# ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────
# Sprint D — sidecar __main__ layering invariant
# ─────────────────────────────────────────────────────────────────────


class TestSidecarMainLayering:
    """middleware/sidecars/__main__.py must never import the langfuse SDK
    directly, and must not import orchestration/components/governance/meta."""

    def test_sidecar_main_does_not_import_langfuse(self) -> None:
        sidecar_main = MIDDLEWARE_DIR / "sidecars" / "__main__.py"
        if not sidecar_main.exists():
            pytest.skip("sidecars/__main__.py not yet scaffolded")
        imports = collect_imports_in_directory(
            MIDDLEWARE_DIR / "sidecars", relative_to=AGENT_ROOT
        )
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "__main__" in str(path) and pkg == "langfuse"
        ]
        assert violations == [], (
            "Sprint D layering violated: sidecars/__main__.py must NOT "
            "import langfuse SDK:\n" + "\n".join(violations)
        )

    def test_sidecar_main_does_not_import_langgraph(self) -> None:
        sidecar_main = MIDDLEWARE_DIR / "sidecars" / "__main__.py"
        if not sidecar_main.exists():
            pytest.skip("sidecars/__main__.py not yet scaffolded")
        imports = collect_imports_in_directory(
            MIDDLEWARE_DIR / "sidecars", relative_to=AGENT_ROOT
        )
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "__main__" in str(path) and pkg == "langgraph"
        ]
        assert violations == [], (
            "Sprint D layering violated: sidecars/__main__.py must NOT "
            "import langgraph:\n" + "\n".join(violations)
        )

    def test_sidecar_main_does_not_import_forbidden_layers(self) -> None:
        sidecar_main = MIDDLEWARE_DIR / "sidecars" / "__main__.py"
        if not sidecar_main.exists():
            pytest.skip("sidecars/__main__.py not yet scaffolded")
        forbidden = {"components", "orchestration", "governance", "meta"}
        imports = collect_imports_in_directory(
            MIDDLEWARE_DIR / "sidecars", relative_to=AGENT_ROOT
        )
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "__main__" in str(path) and pkg in forbidden
        ]
        assert violations == [], (
            "Sprint D layering violated: sidecars/__main__.py must NOT "
            "import components/orchestration/governance/meta:\n" + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# Sprint G — BlackBox pipeline layering invariants
# ─────────────────────────────────────────────────────────────────────


class TestBlackBoxPipelineLayering:
    """Consolidated layering invariants for the BlackBox→Langfuse pipeline.

    Per plan §3, key invariants:
      - black_box_publisher.py has ZERO SDK imports.
      - black_box_to_telemetry.py imports TelemetryExporter port, never langfuse.
      - Both modules must not import langgraph or langchain.
    """

    def test_publisher_has_no_langfuse_import(self) -> None:
        publisher = AGENT_ROOT / "services" / "governance" / "black_box_publisher.py"
        if not publisher.exists():
            pytest.skip("black_box_publisher.py not yet created")
        imports = collect_imports_in_directory(publisher.parent, relative_to=AGENT_ROOT)
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "black_box_publisher" in str(path)
            and pkg in ("langfuse", "langgraph", "langchain")
        ]
        assert violations == [], (
            "Pipeline layering violated: black_box_publisher.py must NOT "
            "import langfuse/langgraph/langchain:\n" + "\n".join(violations)
        )

    def test_relay_has_no_langfuse_import(self) -> None:
        relay = AGENT_ROOT / "middleware" / "sidecars" / "black_box_to_telemetry.py"
        if not relay.exists():
            pytest.skip("black_box_to_telemetry.py not yet created")
        imports = collect_imports_in_directory(relay.parent, relative_to=AGENT_ROOT)
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "black_box_to_telemetry" in str(path)
            and pkg in ("langfuse", "langgraph", "langchain")
        ]
        assert violations == [], (
            "Pipeline layering violated: black_box_to_telemetry.py must NOT "
            "import langfuse/langgraph/langchain:\n" + "\n".join(violations)
        )

    def test_publisher_imports_only_services_layer(self) -> None:
        """black_box_publisher.py may import from services/ only, never
        middleware/, components/, orchestration/, or meta/."""
        publisher = AGENT_ROOT / "services" / "governance" / "black_box_publisher.py"
        if not publisher.exists():
            pytest.skip("black_box_publisher.py not yet created")
        forbidden = {"middleware", "components", "orchestration", "meta"}
        imports = collect_imports_in_directory(publisher.parent, relative_to=AGENT_ROOT)
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "black_box_publisher" in str(path) and pkg in forbidden
        ]
        assert violations == [], (
            "Pipeline layering violated: black_box_publisher.py must NOT "
            "import from upper layers:\n" + "\n".join(violations)
        )

    def test_compliance_publisher_port_has_no_sdk_imports(self) -> None:
        port = AGENT_ROOT / "middleware" / "ports" / "compliance_publisher.py"
        if not port.exists():
            pytest.skip("compliance_publisher.py not yet created")
        imports = collect_imports_in_directory(port.parent, relative_to=AGENT_ROOT)
        violations = [
            f"{path} imports {pkg}"
            for path, pkg in imports
            if "compliance_publisher" in str(path) and pkg in SDK_PACKAGES
        ]
        assert violations == [], (
            "Port purity violated: compliance_publisher.py must NOT "
            "import SDKs:\n" + "\n".join(violations)
        )


# ─────────────────────────────────────────────────────────────────────
# Bridge import allowlist — only stdlib + wire + port
# ─────────────────────────────────────────────────────────────────────


class TestTelemetryBridgeImportAllowlist:
    """telemetry_bridge.py may only import from stdlib, agent_ui_adapter.wire,
    and middleware.ports. No other first-party or third-party packages.
    """

    ALLOWED_FIRST_PARTY = {
        "agent_ui_adapter",
        "middleware",
        "services",
    }

    ALLOWED_MIDDLEWARE_SUBPACKAGES = {
        "middleware.ports",
    }

    ALLOWED_SERVICES_SUBPACKAGES = {
        "services.governance.black_box_publisher",
    }

    def test_bridge_imports_only_allowed_packages(self) -> None:
        bridge = MIDDLEWARE_DIR / "telemetry_bridge.py"
        if not bridge.exists():
            pytest.skip("telemetry_bridge.py not yet created")

        from utils.code_analysis import parse_imports

        parsed = parse_imports(bridge)
        assert parsed["pass"], f"Failed to parse {bridge}"

        violations: list[str] = []
        for imp in parsed["imports"]:
            top = imp["top_package"]
            full_module = imp.get("module", top)

            # stdlib is always allowed
            if self._is_stdlib(top):
                continue

            # Check first-party allowlist
            if top not in self.ALLOWED_FIRST_PARTY:
                violations.append(
                    f"imports '{full_module}' (top: {top}) — not in allowlist"
                )
                continue

            # For middleware imports, only ports subpackage is allowed
            if top == "middleware" and not any(
                full_module.startswith(sub)
                for sub in self.ALLOWED_MIDDLEWARE_SUBPACKAGES
            ):
                violations.append(
                    f"imports '{full_module}' — only middleware.ports allowed"
                )

            # For agent_ui_adapter, only wire subpackage is allowed
            if top == "agent_ui_adapter" and not full_module.startswith(
                "agent_ui_adapter.wire"
            ):
                violations.append(
                    f"imports '{full_module}' — only agent_ui_adapter.wire allowed"
                )

            # Shared PII scrubber (same module the BlackBox relay uses via to_export_kwargs)
            if top == "services" and not any(
                full_module.startswith(sub) for sub in self.ALLOWED_SERVICES_SUBPACKAGES
            ):
                violations.append(
                    f"imports '{full_module}' — only services.governance.black_box_publisher allowed"
                )

        assert violations == [], (
            "telemetry_bridge.py import allowlist violated:\n" + "\n".join(violations)
        )

    @staticmethod
    def _is_stdlib(package: str) -> bool:
        """Check if a package is part of the Python standard library."""
        import sys

        if package in sys.stdlib_module_names:
            return True
        # Common stdlib modules that might not be in stdlib_module_names
        # on all Python versions
        return package in {"__future__", "typing", "logging"}


# ─────────────────────────────────────────────────────────────────────
# Phase 1 (replace-mem0-pgvector) — EmbeddingClient port placement
# ─────────────────────────────────────────────────────────────────────
#
# Per docs/plans/replace_mem0_pgvector.plan.md §Architecture & TDD compliance:
#   (a) EmbeddingClient Protocol defined only in middleware/ports/embedding_client.py
#   (b) litellm (embedding usage) allowed only under middleware/adapters/embedding/
#       (the existing services/llm_*.py litellm import is the sanctioned chat-LLM exception)
#   (c) M-ports stdlib-only invariant still holds for the new port
#
# These assertions extend the existing TestPortPurity / TestSdkConfinement
# coverage without weakening it.


class TestEmbeddingClientPortPlacement:
    """Phase 1: EmbeddingClient must be defined exactly once, in the
    sanctioned port path."""

    def test_protocol_defined_only_in_ports(self) -> None:
        """AST-scan: ``class EmbeddingClient(Protocol)`` may appear only
        in middleware/ports/embedding_client.py.
        """
        canonical = MIDDLEWARE_DIR / "ports" / "embedding_client.py"
        if not canonical.exists():
            pytest.skip("EmbeddingClient port not yet scaffolded")
        violations: list[str] = []
        for py in (AGENT_ROOT).rglob("*.py"):
            if py == canonical:
                continue
            # Skip vendored / venv / hidden tool-state content — .claude/worktrees/
            # holds duplicate agent-session checkouts of this repo.
            sp = str(py)
            rel_parts = py.relative_to(AGENT_ROOT).parts
            if (
                "/site-packages/" in sp
                or "/node_modules/" in sp
                or rel_parts[0] == "venv"
                or any(p.startswith(".") for p in rel_parts[:-1])
            ):
                continue
            try:
                tree = ast.parse(py.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "EmbeddingClient":
                    violations.append(str(py.relative_to(AGENT_ROOT)))
                    break
        assert violations == [], (
            "EmbeddingClient Protocol must be defined only in "
            "middleware/ports/embedding_client.py:\n" + "\n".join(violations)
        )


class TestEmbeddingAdapterPlacement:
    """Phase 1: ``litellm`` (the embedding transport) is allowed in
    middleware/ only under middleware/adapters/embedding/.

    Note: services/llm_*.py imports ``litellm``/``langchain_litellm`` for
    chat completions — that is the *services/* exception sanctioned by
    AGENTS.md rule 4. This rule covers the *middleware/* ring only.
    """

    def test_litellm_only_in_embedding_adapter_within_middleware(self) -> None:
        if not MIDDLEWARE_DIR.exists():
            pytest.skip("middleware/ not yet scaffolded")
        violations: list[str] = []
        for path, pkg in _middleware_imports():
            if pkg != "litellm":
                continue
            path_str = str(path).replace("\\", "/")
            if "middleware/adapters/embedding/" not in path_str:
                violations.append(f"{path} imports litellm")
        assert violations == [], (
            "Phase 1 SDK isolation violated: ``litellm`` may live in "
            "middleware/ only under middleware/adapters/embedding/:\n"
            + "\n".join(violations)
        )

    def test_embedding_port_has_no_sdk_imports(self) -> None:
        """Re-assert M-ports purity for the new port file specifically —
        the EmbeddingClient port MUST be stdlib + typing only.
        """
        port = MIDDLEWARE_DIR / "ports" / "embedding_client.py"
        if not port.exists():
            pytest.skip("EmbeddingClient port not yet scaffolded")
        tree = ast.parse(port.read_text())
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in {"litellm", "openai", "psycopg", "sqlalchemy"}:
                        offenders.append(top)
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if top in {"litellm", "openai", "psycopg", "sqlalchemy"}:
                    offenders.append(top)
        assert offenders == [], (
            "EmbeddingClient port leaked an SDK import — must be stdlib + "
            "typing only:\n" + ", ".join(offenders)
        )
