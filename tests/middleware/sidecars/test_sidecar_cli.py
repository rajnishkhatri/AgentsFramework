"""L2 Contract: Sprint D — CLI sidecar entrypoint (middleware/sidecars/__main__.py).

Tests follow Protocol B (Contract-Driven TDD) from
research/tdd_agentic_systems_prompt.md.

Layer: middleware/sidecars (Middleware ring)
Pyramid level: L2 — Reproducible.  Deterministic, fast, filesystem-isolated.

Test categories:
  A. FAILURE PATHS FIRST — missing env vars, invalid config
  B. CLI ENTRYPOINT STRUCTURE — importable, has run() or main()
  C. REUSES build_adapters — no duplicate wiring logic
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SIDECAR_MAIN = AGENT_ROOT / "middleware" / "sidecars" / "__main__.py"


# ─────────────────────────────────────────────────────────────────────
# A. FAILURE PATHS FIRST — missing env, startup guard
# ─────────────────────────────────────────────────────────────────────


class TestCLIFailurePaths:
    """CLI rejects gracefully when env is misconfigured."""

    def test_missing_langfuse_keys_raises_or_exits(self) -> None:
        """Running the sidecar without Langfuse keys should fail fast."""
        if not SIDECAR_MAIN.exists():
            pytest.skip("sidecars/__main__.py not yet created")

        from middleware.composition import MissingEnvError, build_adapters

        with pytest.raises((MissingEnvError, SystemExit)):
            build_adapters(env={"BLACKBOX_RELAY_MODE": "in_process"})


# ─────────────────────────────────────────────────────────────────────
# B. CLI ENTRYPOINT STRUCTURE — importable module with main()
# ─────────────────────────────────────────────────────────────────────


class TestCLIStructure:
    """The sidecar __main__.py must expose a main() callable."""

    def test_module_exists(self) -> None:
        assert SIDECAR_MAIN.exists(), (
            "middleware/sidecars/__main__.py must exist (Sprint D deliverable)"
        )

    def test_module_defines_main_function(self) -> None:
        if not SIDECAR_MAIN.exists():
            pytest.skip("sidecars/__main__.py not yet created")

        tree = ast.parse(SIDECAR_MAIN.read_text())
        func_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert "main" in func_names, (
            "sidecars/__main__.py must define a main() function"
        )

    def test_module_has_if_name_main_guard(self) -> None:
        if not SIDECAR_MAIN.exists():
            pytest.skip("sidecars/__main__.py not yet created")

        source = SIDECAR_MAIN.read_text()
        assert 'if __name__ == "__main__"' in source or "if __name__ == '__main__'" in source, (
            "sidecars/__main__.py must have an if __name__ == '__main__' guard"
        )


# ─────────────────────────────────────────────────────────────────────
# C. REUSES build_adapters — no duplicate wiring
# ─────────────────────────────────────────────────────────────────────


class TestCLIReusesBuildAdapters:
    """The sidecar CLI must import and use build_adapters from composition,
    not duplicate wiring logic."""

    def test_imports_build_adapters(self) -> None:
        if not SIDECAR_MAIN.exists():
            pytest.skip("sidecars/__main__.py not yet created")

        source = SIDECAR_MAIN.read_text()
        assert "build_adapters" in source, (
            "sidecars/__main__.py must use build_adapters from composition"
        )

    def test_does_not_instantiate_langfuse_exporter_directly(self) -> None:
        if not SIDECAR_MAIN.exists():
            pytest.skip("sidecars/__main__.py not yet created")

        source = SIDECAR_MAIN.read_text()
        assert "LangfuseCloudExporter(" not in source, (
            "sidecars/__main__.py must NOT instantiate LangfuseCloudExporter "
            "directly — use build_adapters() instead"
        )
