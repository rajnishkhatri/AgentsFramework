"""L2 Reproducible: Architectural dependency tests for code reviewer modules.

Verifies that the new modules respect the Four-Layer Architecture:
- trust/review_schema.py imports only from trust/ and allowed stdlib
- utils/code_analysis.py imports only from trust/ and stdlib
"""

from __future__ import annotations

import ast
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestReviewSchemaPlacement:
    """trust/review_schema.py must satisfy T1: zero outward dependencies."""

    def test_imports_only_trust_and_stdlib(self):
        filepath = AGENT_ROOT / "trust" / "review_schema.py"
        assert filepath.exists(), f"Expected {filepath} to exist"

        tree = ast.parse(filepath.read_text())
        allowed_packages = {
            "__future__",
            "datetime",
            "enum",
            "typing",
            "pydantic",
            "trust",
        }

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top not in allowed_packages:
                    violations.append(
                        f"line {node.lineno}: imports {node.module} "
                        f"(top-level: {top})"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in allowed_packages:
                        violations.append(
                            f"line {node.lineno}: imports {alias.name} "
                            f"(top-level: {top})"
                        )

        assert violations == [], (
            "trust/review_schema.py has forbidden imports:\n"
            + "\n".join(violations)
        )

    def test_no_io_imports(self):
        filepath = AGENT_ROOT / "trust" / "review_schema.py"
        tree = ast.parse(filepath.read_text())
        io_modules = {
            "os", "logging", "pathlib", "subprocess", "requests",
            "socket", "http", "urllib", "io", "tempfile",
        }

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in io_modules:
                    violations.append(
                        f"line {node.lineno}: imports I/O module {node.module}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in io_modules:
                        violations.append(
                            f"line {node.lineno}: imports I/O module {alias.name}"
                        )

        assert violations == [], (
            "trust/review_schema.py imports I/O modules:\n"
            + "\n".join(violations)
        )


class TestCodeAnalysisPlacement:
    """utils/code_analysis.py must not import from agents/ or governance/."""

    def test_imports_only_trust_and_stdlib(self):
        filepath = AGENT_ROOT / "utils" / "code_analysis.py"
        assert filepath.exists(), f"Expected {filepath} to exist"

        tree = ast.parse(filepath.read_text())
        forbidden_packages = {"agents", "governance"}

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in forbidden_packages:
                    violations.append(
                        f"line {node.lineno}: imports {node.module} "
                        f"(forbidden: {top})"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in forbidden_packages:
                        violations.append(
                            f"line {node.lineno}: imports {alias.name} "
                            f"(forbidden: {top})"
                        )

        assert violations == [], (
            "utils/code_analysis.py imports from forbidden layers:\n"
            + "\n".join(violations)
        )

    def test_uses_only_stdlib_externals(self):
        """code_analysis.py should use only ast and pathlib from stdlib."""
        filepath = AGENT_ROOT / "utils" / "code_analysis.py"
        tree = ast.parse(filepath.read_text())

        allowed_packages = {
            "__future__",
            "ast",
            "pathlib",
            "typing",
            "trust",
        }

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top not in allowed_packages:
                    violations.append(
                        f"line {node.lineno}: imports {node.module} "
                        f"(top-level: {top})"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in allowed_packages:
                        violations.append(
                            f"line {node.lineno}: imports {alias.name} "
                            f"(top-level: {top})"
                        )

        assert violations == [], (
            "utils/code_analysis.py uses non-stdlib/non-trust packages:\n"
            + "\n".join(violations)
        )
