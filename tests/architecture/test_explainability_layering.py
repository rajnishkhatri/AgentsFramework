"""Architecture test: ExplainabilityService import boundaries.

AC5: services/explainability_service.py has zero imports from components/,
orchestration/, agent_ui_adapter/, middleware/, or any frontend project.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SERVICE_FILE = (
    Path(__file__).resolve().parents[2] / "services" / "explainability_service.py"
)

FORBIDDEN_PREFIXES = (
    "components",
    "orchestration",
    "agent_ui_adapter",
    "middleware",
    "frontend",
    "frontend_explainability",
    "frontend-explainability",
)


def _collect_imports(filepath: Path) -> list[str]:
    tree = ast.parse(filepath.read_text())
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def test_explainability_service_has_no_forbidden_imports() -> None:
    assert SERVICE_FILE.exists(), f"{SERVICE_FILE} does not exist"
    imports = _collect_imports(SERVICE_FILE)
    violations = [
        imp
        for imp in imports
        if any(imp == prefix or imp.startswith(prefix + ".") for prefix in FORBIDDEN_PREFIXES)
    ]
    assert violations == [], (
        f"services/explainability_service.py has forbidden imports: {violations}"
    )


def test_explainability_service_exists() -> None:
    assert SERVICE_FILE.exists()
