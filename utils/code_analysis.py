"""Deterministic AST-based code analysis tools for the Code Review Agent.

Horizontal service (utils/) -- uses only ``ast`` and ``pathlib`` from
stdlib plus ``trust/`` foundation types.  No external dependencies.

Each tool returns a structured dict compatible with the semi-formal
certificate format: ``{pass: bool, violations: [...]}``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

LAYER_DIRS = {
    "trust": "Trust Foundation",
    "utils": "Horizontal Services",
    "services": "Horizontal Services",
    "components": "Vertical Components",
    "agents": "Vertical Components",
    "orchestration": "Orchestration",
    "governance": "Meta-Layer",
    "meta": "Meta-Layer",
}

# Authoritative layer dependency rules (STORY-411 reconciliation).
# Each key is a source layer; each value is the set of top-level
# packages it MUST NOT import. The meta-layer (AP8) must never call
# orchestration. Tests in tests/architecture/ consume this same dict
# via ``check_dependency_rules`` so the boundary definition lives in
# exactly one place.
FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "trust": {"utils", "services", "components", "agents",
              "orchestration", "governance", "meta"},
    "utils": {"components", "agents", "orchestration",
              "governance", "meta"},
    "services": {"components", "agents", "orchestration", "meta"},
    "components": {"orchestration", "meta"},
    "agents": {"orchestration", "governance", "meta"},
    "meta": {"orchestration"},
}

FRAMEWORK_FORBIDDEN: dict[str, set[str]] = {
    "components": {"langgraph", "langchain", "langchain_core",
                   "langchain_community"},
    "services": {"langgraph", "langchain", "langchain_core",
                 "langchain_community"},
}

IO_MODULES = frozenset({
    "os",
    "shutil",
    "socket",
    "http",
    "urllib",
    "requests",
    "httpx",
    "aiohttp",
    "boto3",
    "botocore",
    "sqlite3",
    "sqlalchemy",
    "redis",
    "pymongo",
    "logging",
    "pathlib",
    "subprocess",
    "tempfile",
    "io",
})

TRUST_ALLOWED_STDLIB = frozenset({
    "__future__",
    "datetime",
    "enum",
    "typing",
    "dataclasses",
    "hashlib",
    "hmac",
    "json",
    "re",
    "abc",
    "collections",
    "functools",
    "uuid",
    "copy",
    "math",
})


def parse_imports(filepath: str | Path) -> dict[str, Any]:
    """Extract all imports from a Python file via AST.

    Returns::

        {
            "pass": True,
            "file": "<filepath>",
            "imports": [
                {"module": "trust.models", "names": ["AgentFacts"], "line": 5},
                ...
            ]
        }
    """
    filepath = Path(filepath)
    imports: list[dict[str, Any]] = []
    try:
        tree = ast.parse(filepath.read_text())
    except (SyntaxError, FileNotFoundError) as exc:
        return {
            "pass": False,
            "file": str(filepath),
            "imports": [],
            "violations": [
                {"rule": "PARSE", "file": str(filepath), "line": 0,
                 "description": f"Could not parse file: {exc}"}
            ],
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [alias.name for alias in node.names]
            imports.append({
                "module": node.module,
                "names": names,
                "line": node.lineno,
                "top_package": node.module.split(".")[0],
            })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "module": alias.name,
                    "names": [alias.asname or alias.name],
                    "line": node.lineno,
                    "top_package": alias.name.split(".")[0],
                })

    return {"pass": True, "file": str(filepath), "imports": imports}


def classify_layer(filepath: str | Path) -> dict[str, Any]:
    """Map a file path to a grid layer using directory convention.

    Returns::

        {"file": "<filepath>", "layer": "Trust Foundation", "layer_dir": "trust"}
    """
    filepath = Path(filepath)
    parts = filepath.parts
    for part in parts:
        if part in LAYER_DIRS:
            return {
                "file": str(filepath),
                "layer": LAYER_DIRS[part],
                "layer_dir": part,
            }
    return {
        "file": str(filepath),
        "layer": "Unknown",
        "layer_dir": "",
    }


def check_dependency_rules(filepath: str | Path) -> dict[str, Any]:
    """Validate all imports against the dependency table.

    Checks the 11 dependency rules from the Four-Layer Architecture:
    - trust/ must not import from utils/, agents/, governance/
    - utils/ must not import from agents/, governance/
    """
    filepath = Path(filepath)
    layer_info = classify_layer(filepath)
    layer_dir = layer_info["layer_dir"]

    if layer_dir not in FORBIDDEN_IMPORTS:
        return {
            "pass": True,
            "file": str(filepath),
            "layer": layer_info["layer"],
            "violations": [],
        }

    import_result = parse_imports(filepath)
    if not import_result["pass"]:
        return {
            "pass": False,
            "file": str(filepath),
            "layer": layer_info["layer"],
            "violations": import_result.get("violations", []),
        }

    forbidden = FORBIDDEN_IMPORTS[layer_dir]
    violations: list[dict[str, Any]] = []

    for imp in import_result["imports"]:
        top_pkg = imp["top_package"]
        if top_pkg in forbidden:
            violations.append({
                "rule": f"DEP.{layer_dir}_cannot_import_{top_pkg}",
                "file": str(filepath),
                "line": imp["line"],
                "description": (
                    f"{layer_info['layer']} ({layer_dir}/) imports "
                    f"from {LAYER_DIRS.get(top_pkg, top_pkg)} ({top_pkg}/)"
                ),
            })

    return {
        "pass": len(violations) == 0,
        "file": str(filepath),
        "layer": layer_info["layer"],
        "violations": violations,
    }


def collect_imports_in_directory(
    source_dir: str | Path,
    *,
    relative_to: str | Path | None = None,
) -> list[tuple[str, str]]:
    """Walk ``source_dir`` recursively and yield ``(file_path, top_package)`` pairs.

    Used by ``tests/architecture/test_dependency_rules.py`` so the test
    harness, ``meta/code_reviewer.py``, and any future caller all share the
    same AST-based import-extraction logic.

    The returned ``file_path`` is rendered relative to ``relative_to`` when
    provided (else the absolute path is returned). Files that fail to parse
    are skipped silently — the caller is responsible for narrower diagnostics
    when needed.
    """
    source_dir = Path(source_dir)
    base = Path(relative_to) if relative_to is not None else None
    pairs: list[tuple[str, str]] = []
    for py_file in source_dir.rglob("*.py"):
        parsed = parse_imports(py_file)
        if not parsed["pass"]:
            continue
        try:
            display_path = (
                str(py_file.relative_to(base)) if base is not None else str(py_file)
            )
        except ValueError:
            display_path = str(py_file)
        for imp in parsed["imports"]:
            pairs.append((display_path, imp["top_package"]))
    return pairs


def check_trust_purity(filepath: str | Path) -> dict[str, Any]:
    """Verify no I/O, logging, storage, or network imports in trust/ files.

    Trust Foundation modules must be pure data and pure functions.
    Only stdlib modules from the allow-list and ``pydantic`` are permitted.
    """
    filepath = Path(filepath)
    layer_info = classify_layer(filepath)

    if layer_info["layer_dir"] != "trust":
        return {
            "pass": True,
            "file": str(filepath),
            "layer": layer_info["layer"],
            "violations": [],
            "note": "Not a trust/ file; purity check skipped.",
        }

    import_result = parse_imports(filepath)
    if not import_result["pass"]:
        return {
            "pass": False,
            "file": str(filepath),
            "layer": layer_info["layer"],
            "violations": import_result.get("violations", []),
        }

    violations: list[dict[str, Any]] = []
    for imp in import_result["imports"]:
        top_pkg = imp["top_package"]
        if top_pkg in IO_MODULES:
            violations.append({
                "rule": "TRUST_PURITY.io_import",
                "file": str(filepath),
                "line": imp["line"],
                "description": (
                    f"trust/ file imports I/O module '{imp['module']}' "
                    f"(top-level: {top_pkg})"
                ),
            })

    return {
        "pass": len(violations) == 0,
        "file": str(filepath),
        "layer": layer_info["layer"],
        "violations": violations,
    }


def check_protocol_conformance(
    adapter_filepath: str | Path,
    protocol_name: str,
) -> dict[str, Any]:
    """Verify an adapter implements all methods declared in a protocol.

    Parses the adapter file and the protocol definition via AST to
    compare method signatures.
    """
    adapter_filepath = Path(adapter_filepath)

    try:
        adapter_tree = ast.parse(adapter_filepath.read_text())
    except (SyntaxError, FileNotFoundError) as exc:
        return {
            "pass": False,
            "file": str(adapter_filepath),
            "protocol": protocol_name,
            "violations": [
                {"rule": "PROTOCOL.parse_error", "file": str(adapter_filepath),
                 "line": 0, "description": f"Could not parse adapter: {exc}"}
            ],
        }

    protocol_filepath = _find_protocol_file(adapter_filepath)
    if protocol_filepath is None:
        return {
            "pass": False,
            "file": str(adapter_filepath),
            "protocol": protocol_name,
            "violations": [
                {"rule": "PROTOCOL.not_found", "file": str(adapter_filepath),
                 "line": 0,
                 "description": f"Could not locate protocols.py for {protocol_name}"}
            ],
        }

    try:
        protocol_tree = ast.parse(protocol_filepath.read_text())
    except SyntaxError as exc:
        return {
            "pass": False,
            "file": str(adapter_filepath),
            "protocol": protocol_name,
            "violations": [
                {"rule": "PROTOCOL.parse_error", "file": str(protocol_filepath),
                 "line": 0, "description": f"Could not parse protocols: {exc}"}
            ],
        }

    protocol_methods = _extract_class_methods(protocol_tree, protocol_name)
    if not protocol_methods:
        return {
            "pass": False,
            "file": str(adapter_filepath),
            "protocol": protocol_name,
            "violations": [
                {"rule": "PROTOCOL.class_not_found", "file": str(protocol_filepath),
                 "line": 0,
                 "description": f"Protocol class '{protocol_name}' not found"}
            ],
        }

    adapter_methods: set[str] = set()
    for node in ast.walk(adapter_tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    adapter_methods.add(item.name)

    missing = protocol_methods - adapter_methods
    violations: list[dict[str, Any]] = []
    for method in sorted(missing):
        violations.append({
            "rule": "PROTOCOL.missing_method",
            "file": str(adapter_filepath),
            "line": 0,
            "description": (
                f"Adapter is missing method '{method}' "
                f"required by protocol '{protocol_name}'"
            ),
        })

    return {
        "pass": len(violations) == 0,
        "file": str(adapter_filepath),
        "protocol": protocol_name,
        "missing_methods": sorted(missing),
        "violations": violations,
    }


def detect_anti_patterns(filepath: str | Path) -> dict[str, Any]:
    """Heuristic checks for AP1-AP9 anti-patterns via AST analysis.

    Detects:
    - AP2: Vertical-to-vertical imports (agents/ importing from agents/)
    - AP3: Hardcoded prompt strings (f-strings assigned to prompt vars)
    - AP5: Direct file I/O in vertical components (open() calls)
    - AP6: Pydantic BaseModel definitions inside utils/
    - AP9: Mixing signed/unsigned metadata patterns
    """
    filepath = Path(filepath)

    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (SyntaxError, FileNotFoundError) as exc:
        return {
            "pass": False,
            "file": str(filepath),
            "violations": [
                {"rule": "AP.PARSE", "file": str(filepath), "line": 0,
                 "description": f"Could not parse file: {exc}"}
            ],
        }

    layer_info = classify_layer(filepath)
    violations: list[dict[str, Any]] = []

    # AP2: Vertical-to-vertical import
    if layer_info["layer_dir"] == "agents":
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] == "agents":
                    violations.append({
                        "rule": "AP2",
                        "file": str(filepath),
                        "line": node.lineno,
                        "description": (
                            f"Vertical-to-vertical import: agents/ file "
                            f"imports from agents/ ({node.module})"
                        ),
                    })

    # AP3: Hardcoded prompts -- f-strings containing prompt-like keywords
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                target_name = ""
                if isinstance(target, ast.Name):
                    target_name = target.id
                elif isinstance(target, ast.Attribute):
                    target_name = target.attr
                if any(kw in target_name.lower() for kw in ("prompt", "system_prompt", "instruction")):
                    if isinstance(node.value, ast.JoinedStr):
                        violations.append({
                            "rule": "AP3",
                            "file": str(filepath),
                            "line": node.lineno,
                            "description": (
                                f"Hardcoded prompt f-string assigned to "
                                f"'{target_name}' -- use a .j2 template"
                            ),
                        })

    # AP5: Direct file I/O in vertical components
    if layer_info["layer_dir"] == "agents":
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = _get_call_name(node)
                if func_name == "open":
                    violations.append({
                        "rule": "AP5",
                        "file": str(filepath),
                        "line": node.lineno,
                        "description": (
                            "Direct open() call in vertical component -- "
                            "use a horizontal service for I/O"
                        ),
                    })

    # AP6: Pydantic BaseModel in utils/
    if layer_info["layer_dir"] == "utils":
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if base_name == "BaseModel":
                        violations.append({
                            "rule": "AP6",
                            "file": str(filepath),
                            "line": node.lineno,
                            "description": (
                                f"Pydantic BaseModel '{node.name}' defined "
                                f"in utils/ -- shared models belong in trust/"
                            ),
                        })

    return {
        "pass": len(violations) == 0,
        "file": str(filepath),
        "violations": violations,
    }


# ── Private helpers ────────────────────────────────────────────────────


def _find_protocol_file(adapter_filepath: Path) -> Path | None:
    """Walk upward from adapter to find trust/protocols.py."""
    current = adapter_filepath.parent
    for _ in range(10):
        candidate = current / "trust" / "protocols.py"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _extract_class_methods(tree: ast.Module, class_name: str) -> set[str]:
    """Extract method names defined in a class (excluding dunder methods)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods: set[str] = set()
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_"):
                        methods.add(item.name)
            return methods
    return set()


def _get_call_name(node: ast.Call) -> str:
    """Extract the function name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""
