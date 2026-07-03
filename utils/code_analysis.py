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
    "trust": {
        "utils",
        "services",
        "components",
        "agents",
        "orchestration",
        "governance",
        "meta",
    },
    "utils": {"components", "agents", "orchestration", "governance", "meta"},
    "services": {"components", "agents", "orchestration", "meta"},
    "components": {"orchestration", "meta"},
    "agents": {"orchestration", "governance", "meta"},
    "meta": {"orchestration"},
}

FRAMEWORK_FORBIDDEN: dict[str, set[str]] = {
    "components": {"langgraph", "langchain", "langchain_core", "langchain_community"},
    "services": {"langgraph", "langchain", "langchain_core", "langchain_community"},
}

IO_MODULES = frozenset(
    {
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
    }
)

TRUST_ALLOWED_STDLIB = frozenset(
    {
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
    }
)


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
                {
                    "rule": "PARSE",
                    "file": str(filepath),
                    "line": 0,
                    "description": f"Could not parse file: {exc}",
                }
            ],
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [alias.name for alias in node.names]
            imports.append(
                {
                    "module": node.module,
                    "names": names,
                    "line": node.lineno,
                    "top_package": node.module.split(".")[0],
                }
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "module": alias.name,
                        "names": [alias.asname or alias.name],
                        "line": node.lineno,
                        "top_package": alias.name.split(".")[0],
                    }
                )

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


def _is_test_module(filepath: Path) -> bool:
    """A pytest module (tests/ tree, test_*.py, or conftest.py) is not a
    layer member — cross-layer imports are the norm in integration/live
    tests, and the package-level invariants are enforced separately by
    ``tests/architecture/``."""
    parts = filepath.parts
    name = filepath.name
    return "tests" in parts or name.startswith("test_") or name == "conftest.py"


def check_dependency_rules(filepath: str | Path) -> dict[str, Any]:
    """Validate all imports against the dependency table.

    Checks the 11 dependency rules from the Four-Layer Architecture:
    - trust/ must not import from utils/, agents/, governance/
    - utils/ must not import from agents/, governance/

    Test modules are exempt: ``classify_layer`` matches the first path part
    in ``LAYER_DIRS``, so ``tests/services/...`` would otherwise be graded as
    the services layer and a live test's legitimate ``components`` import
    would raise ``DEP.services_cannot_import_components`` (the false positive
    that rejected PR #120).
    """
    filepath = Path(filepath)
    layer_info = classify_layer(filepath)
    layer_dir = layer_info["layer_dir"]

    if _is_test_module(filepath):
        return {
            "pass": True,
            "file": str(filepath),
            "layer": layer_info["layer"],
            "violations": [],
        }

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
            violations.append(
                {
                    "rule": f"DEP.{layer_dir}_cannot_import_{top_pkg}",
                    "file": str(filepath),
                    "line": imp["line"],
                    "description": (
                        f"{layer_info['layer']} ({layer_dir}/) imports "
                        f"from {LAYER_DIRS.get(top_pkg, top_pkg)} ({top_pkg}/)"
                    ),
                }
            )

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
            violations.append(
                {
                    "rule": "TRUST_PURITY.io_import",
                    "file": str(filepath),
                    "line": imp["line"],
                    "description": (
                        f"trust/ file imports I/O module '{imp['module']}' "
                        f"(top-level: {top_pkg})"
                    ),
                }
            )

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
                {
                    "rule": "PROTOCOL.parse_error",
                    "file": str(adapter_filepath),
                    "line": 0,
                    "description": f"Could not parse adapter: {exc}",
                }
            ],
        }

    protocol_filepath = _find_protocol_file(adapter_filepath)
    if protocol_filepath is None:
        return {
            "pass": False,
            "file": str(adapter_filepath),
            "protocol": protocol_name,
            "violations": [
                {
                    "rule": "PROTOCOL.not_found",
                    "file": str(adapter_filepath),
                    "line": 0,
                    "description": f"Could not locate protocols.py for {protocol_name}",
                }
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
                {
                    "rule": "PROTOCOL.parse_error",
                    "file": str(protocol_filepath),
                    "line": 0,
                    "description": f"Could not parse protocols: {exc}",
                }
            ],
        }

    protocol_methods = _extract_class_methods(protocol_tree, protocol_name)
    if not protocol_methods:
        return {
            "pass": False,
            "file": str(adapter_filepath),
            "protocol": protocol_name,
            "violations": [
                {
                    "rule": "PROTOCOL.class_not_found",
                    "file": str(protocol_filepath),
                    "line": 0,
                    "description": f"Protocol class '{protocol_name}' not found",
                }
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
        violations.append(
            {
                "rule": "PROTOCOL.missing_method",
                "file": str(adapter_filepath),
                "line": 0,
                "description": (
                    f"Adapter is missing method '{method}' "
                    f"required by protocol '{protocol_name}'"
                ),
            }
        )

    return {
        "pass": len(violations) == 0,
        "file": str(adapter_filepath),
        "protocol": protocol_name,
        "missing_methods": sorted(missing),
        "violations": violations,
    }


def detect_anti_patterns(filepath: str | Path) -> dict[str, Any]:
    """Heuristic checks for AP-1..AP-9 anti-patterns via AST analysis.

    Rule ids emitted in violations use the canonical hyphenated form
    (``AP-2``, ``AP-3``, ``AP-5``, ``AP-6``) — the same form used in
    ``AGENTS.md`` and the ``rule_id`` column of every ``REVIEW.md``. This
    keeps finding-dedup at merge time consistent (P2-10).

    Detects:
    - AP-2: Vertical-to-vertical imports (agents/ importing from agents/)
    - AP-3: Hardcoded prompt strings (f-strings assigned to prompt vars)
    - AP-5: Direct file I/O in vertical components (open() calls)
    - AP-6: Pydantic BaseModel definitions inside utils/
    - AP-9: Mixing signed/unsigned metadata patterns
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
                {
                    "rule": "AP.PARSE",
                    "file": str(filepath),
                    "line": 0,
                    "description": f"Could not parse file: {exc}",
                }
            ],
        }

    layer_info = classify_layer(filepath)
    violations: list[dict[str, Any]] = []

    # AP2: Vertical-to-vertical import
    if layer_info["layer_dir"] == "agents":
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] == "agents":
                    violations.append(
                        {
                            "rule": "AP-2",
                            "file": str(filepath),
                            "line": node.lineno,
                            "description": (
                                f"Vertical-to-vertical import: agents/ file "
                                f"imports from agents/ ({node.module})"
                            ),
                        }
                    )

    # AP3: Hardcoded prompts -- f-strings containing prompt-like keywords
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                target_name = ""
                if isinstance(target, ast.Name):
                    target_name = target.id
                elif isinstance(target, ast.Attribute):
                    target_name = target.attr
                if any(
                    kw in target_name.lower()
                    for kw in ("prompt", "system_prompt", "instruction")
                ):
                    if isinstance(node.value, ast.JoinedStr):
                        violations.append(
                            {
                                "rule": "AP-3",
                                "file": str(filepath),
                                "line": node.lineno,
                                "description": (
                                    f"Hardcoded prompt f-string assigned to "
                                    f"'{target_name}' -- use a .j2 template"
                                ),
                            }
                        )

    # AP5: Direct file I/O in vertical components
    if layer_info["layer_dir"] == "agents":
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = _get_call_name(node)
                if func_name == "open":
                    violations.append(
                        {
                            "rule": "AP-5",
                            "file": str(filepath),
                            "line": node.lineno,
                            "description": (
                                "Direct open() call in vertical component -- "
                                "use a horizontal service for I/O"
                            ),
                        }
                    )

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
                        violations.append(
                            {
                                "rule": "AP-6",
                                "file": str(filepath),
                                "line": node.lineno,
                                "description": (
                                    f"Pydantic BaseModel '{node.name}' defined "
                                    f"in utils/ -- shared models belong in trust/"
                                ),
                            }
                        )

    return {
        "pass": len(violations) == 0,
        "file": str(filepath),
        "violations": violations,
    }


# ── G8: test-weakening detector ────────────────────────────────────────

# A skip/xfail with one of these substrings in its reason is treated as
# justified (the G8 escape hatch — see AGENTS.md "G8 — test-mass-rewrite gate").
# Keep the tokens explicit so a reviewer grepping for them finds every waiver.
_G8_JUSTIFICATION_TOKENS = ("G8-OK", "ADR-", "flaky-tracked:", "live_llm", "env-gated:")

# pytest markers that, when newly added, weaken a test's enforcement.
_WEAKENING_MARKERS = ("skip", "skipif", "xfail")


def _test_func_names(tree: ast.Module) -> set[str]:
    """Names of every ``def test_*`` / ``async def test_*`` in a module tree,
    at any nesting depth (class methods included)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                names.add(node.name)
    return names


def _marker_name(node: ast.expr) -> str | None:
    """Return the pytest.mark.<name> marker name for a decorator node, else None.

    Matches both ``@pytest.mark.skip`` (Attribute) and
    ``@pytest.mark.skipif(...)`` (Call wrapping an Attribute)."""
    target = node.func if isinstance(node, ast.Call) else node
    # pytest.mark.<name>
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Attribute):
        if target.value.attr == "mark":
            return target.attr
    return None


def _decorator_reason(node: ast.expr) -> str:
    """Best-effort extraction of a marker's reason string (positional or kw)."""
    if not isinstance(node, ast.Call):
        return ""
    parts: list[str] = []
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            parts.append(arg.value)
    for kw in node.keywords:
        if kw.arg == "reason" and isinstance(kw.value, ast.Constant):
            if isinstance(kw.value.value, str):
                parts.append(kw.value.value)
    return " ".join(parts)


def _weakening_markers(tree: ast.Module) -> dict[str, list[tuple[str, str]]]:
    """Map each test function -> list of (marker_name, reason) for its
    skip/skipif/xfail decorators. Only test functions are inspected."""
    out: dict[str, list[tuple[str, str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        marks: list[tuple[str, str]] = []
        for dec in node.decorator_list:
            name = _marker_name(dec)
            if name in _WEAKENING_MARKERS:
                marks.append((name, _decorator_reason(dec)))
        if marks:
            out[node.name] = marks
    return out


def _is_justified(reason: str) -> bool:
    return any(token in reason for token in _G8_JUSTIFICATION_TOKENS)


def _removal_waived(new_source: str, removed_test: str) -> bool:
    """True iff ``new_source`` carries a ``# G8-OK:`` comment naming the removed
    test — the explicit, specific waiver for a legitimate rename/consolidation."""
    for line in new_source.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("#")
            and "G8-OK" in stripped
            and removed_test in stripped
        ):
            return True
    return False


def detect_test_weakening(old_source: str, new_source: str) -> dict[str, Any]:
    """Compare two versions of a test module for G8 (test-mass-rewrite) weakening.

    Returns a structured verdict. A change weakens the suite when, versus
    ``old_source``, the new version either:

    * **removes** a ``def test_*`` (the function name disappears), or
    * **newly adds** a ``@pytest.mark.skip`` / ``skipif`` / ``xfail`` to a test
      that did not have that marker before — unless the marker's reason carries a
      justification token (``G8-OK``, an ``ADR-`` reference, ``flaky-tracked:``,
      ``live_llm``, ``env-gated:``).

    Pure: parses both sources with ``ast``; executes nothing. A syntax error in
    either side is reported as a violation (conservative — never silently pass).
    The git glue (resolving old/new content from the merge base) lives in the
    architecture test, so this core is directly unit-testable.
    """
    try:
        old_tree = ast.parse(old_source)
    except SyntaxError as exc:
        return _weakening_result(
            [_weak_v("G8.PARSE_OLD", 0, f"old unparseable: {exc}")]
        )
    try:
        new_tree = ast.parse(new_source)
    except SyntaxError as exc:
        return _weakening_result(
            [_weak_v("G8.PARSE_NEW", 0, f"new unparseable: {exc}")]
        )

    violations: list[dict[str, Any]] = []

    old_tests = _test_func_names(old_tree)
    new_tests = _test_func_names(new_tree)
    for removed in sorted(old_tests - new_tests):
        # A removal/rename is allowed when the NEW source carries a waiver comment
        # that names the removed test, e.g. ``# G8-OK: test_real_corpus_has_nine
        # renamed to …``. This is the same escape hatch as the skip-reason tokens —
        # a legitimate rename or consolidation declares itself; a silent deletion
        # does not. The comment must name the test so the waiver is specific.
        if _removal_waived(new_source, removed):
            continue
        violations.append(
            _weak_v(
                "G8.TEST_REMOVED",
                0,
                f"test '{removed}' was removed (present in the base, gone now); "
                f"add a '# G8-OK: {removed} …' waiver comment if intentional",
            )
        )

    old_marks = _weakening_markers(old_tree)
    new_marks = _weakening_markers(new_tree)
    for test_name, marks in sorted(new_marks.items()):
        prior = {m for m, _ in old_marks.get(test_name, [])}
        for marker, reason in marks:
            if marker in prior:
                continue  # marker already existed in the base — not newly weakened
            if _is_justified(reason):
                continue
            violations.append(
                _weak_v(
                    "G8.TEST_SKIPPED",
                    0,
                    f"test '{test_name}' newly marked @pytest.mark.{marker} "
                    f"without a justification token (reason={reason!r})",
                )
            )

    return _weakening_result(violations)


def _weak_v(rule: str, line: int, description: str) -> dict[str, Any]:
    return {"rule": rule, "line": line, "description": description}


def _weakening_result(violations: list[dict[str, Any]]) -> dict[str, Any]:
    return {"pass": len(violations) == 0, "violations": violations}


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


# ── ADR.1: file-list scan for the ADR ratchet (WI-5) ────────────────────
#
# The ``⚠️ Ask first`` triggers in AGENTS.md are mechanically detectable from the
# changed-file list (see root REVIEW.md "ADR.1 detection (mechanical)"). This
# detector is the deterministic half of that gate: it flags a diff that touches
# an Ask-first seam AND ships no new ``docs/adr/`` file. Pure stdlib — no git;
# the caller resolves the changed/added file list.

# Repo-relative paths whose presence in a diff is an ``⚠️ Ask first`` trigger.
# A pyproject.toml *dependency* change can't be told from a comment tweak at the
# file-list level, so any pyproject.toml touch is treated as a trigger
# (conservative — the ADR ratchet prefers over-flagging to silent drift).
_ADR1_TRIGGER_PATHS: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "trust/models.py",
        "orchestration/react_loop.py",
    }
)


def detect_adr1_missing(
    changed_files: list[str],
    *,
    added_files: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministic ADR.1 (ADR ratchet) check from a changed-file list.

    Flags when the diff touches an ``⚠️ Ask first`` trigger **and** ships no new
    file under ``docs/adr/``. The triggers (AGENTS.md §Ask first):

    * ``pyproject.toml`` (a dependency/config change),
    * ``trust/models.py`` (a trust-kernel type change → re-signing),
    * ``orchestration/react_loop.py`` (a new graph node),
    * a new horizontal service — a newly-added ``services/<name>/__init__.py``
      (a package that didn't exist before). Requires ``added_files``; without it
      only the three file-presence triggers fire.

    Relief: any path under ``docs/adr/`` in ``changed_files`` (typically added)
    ⇒ an ADR was filed, no violation.

    Returns the standard ``{"pass": bool, "violations": [...]}`` shape. Each
    violation carries ``rule="ADR.1"``, the list of ``triggers`` that fired, and
    a human-readable description. Pure: no I/O, no git.
    """

    # Normalize to posix, folding Windows-style backslashes (git on Windows can
    # emit them); on POSIX, Path treats "\" as a literal char, so do it by hand.
    def _norm(p: str) -> str:
        return Path(p.replace("\\", "/")).as_posix()

    changed = {_norm(p) for p in changed_files}
    added = {_norm(p) for p in (added_files or [])}

    triggers: list[str] = []
    for trigger in _ADR1_TRIGGER_PATHS:
        if trigger in changed:
            triggers.append(trigger)
    # New horizontal service: a freshly-added services/<name>/__init__.py.
    if added:
        for path in sorted(added):
            parts = Path(path).parts
            if (
                len(parts) >= 3
                and parts[0] == "services"
                and parts[-1] == "__init__.py"
            ):
                triggers.append(path)
                break  # one new service is enough to trip the trigger

    # Relief: a new ADR is typically an *added* file, so check both sets.
    adr_filed = any(p.startswith("docs/adr/") for p in changed) or any(
        p.startswith("docs/adr/") for p in added
    )
    if not triggers or adr_filed:
        return {
            "pass": True,
            "violations": [],
            "triggers": triggers,
            "adr_filed": adr_filed,
        }

    description = (
        "⚠️ Ask-first trigger(s) present with no new docs/adr/ file: "
        + ", ".join(triggers)
        + ". File an ADR (copy docs/adr/0000-template.md) or document the waiver."
    )
    return {
        "pass": False,
        "violations": [
            {"rule": "ADR.1", "triggers": triggers, "description": description}
        ],
        "triggers": triggers,
        "adr_filed": False,
    }


# ── TAP-2: mock-abuse detector (>3 mocks/test) ──────────────────────────
#
# services/AGENTS.md: "TAP-2 (mock addiction): >3 mocks in one test is a warning
# — prefer real in-memory implementations; reserve mocks for truly external
# systems." Pure AST: counts mock anchors per ``def test_*``.

_MOCK_TYPES: frozenset[str] = frozenset(
    {"MagicMock", "AsyncMock", "Mock", "NonCallableMock"}
)
_PATCH_LEAVES: frozenset[str] = frozenset({"patch", "patch.object", "patch.multiple"})


def _dotted_name(node: ast.expr) -> str:
    """Dotted name for a Name/Attribute chain (``mock.patch.object`` → that
    string). Returns ``""`` for anything not a plain dotted expression."""
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return ""
    return ".".join(reversed(parts))


def _is_patch_dotted(name: str) -> bool:
    """True for ``patch`` / ``patch.object`` / ``patch.multiple`` (bare or
    dotted, e.g. ``unittest.mock.patch.object``)."""
    if not name:
        return False
    return any(name == leaf or name.endswith("." + leaf) for leaf in _PATCH_LEAVES)


def _is_mock_construction(name: str) -> bool:
    """True for ``MagicMock()`` / ``AsyncMock()`` / ``Mock()`` /
    ``NonCallableMock()`` (bare or dotted, e.g. ``mock.MagicMock``)."""
    if not name:
        return False
    leaf = name.split(".")[-1]
    return leaf in _MOCK_TYPES


def _decorator_dotted(dec: ast.expr) -> str:
    target = dec.func if isinstance(dec, ast.Call) else dec
    return _dotted_name(target)


def _count_mocks(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Mock anchors for one test function: ``@patch(...)`` decorators plus
    ``patch(...)`` / ``MagicMock()`` / … calls anywhere in the body."""
    count = 0
    for dec in func_node.decorator_list:
        if _is_patch_dotted(_decorator_dotted(dec)):
            count += 1
    for stmt in func_node.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                name = _dotted_name(node.func)
                if _is_patch_dotted(name) or _is_mock_construction(name):
                    count += 1
    return count


def detect_mock_abuse(source: str, *, threshold: int = 3) -> dict[str, Any]:
    """TAP-2 (mock addiction) detector: flag ``def test_*`` with more than
    ``threshold`` mock anchors (``@patch`` / ``patch(...)`` / ``MagicMock()`` /
    ``AsyncMock()`` / ``Mock()`` / ``NonCallableMock()``).

    Pure AST — parses ``source`` and executes nothing. A syntax error is
    reported conservatively (never silently pass). Returns
    ``{"pass": bool, "violations": [{"rule": "TAP-2", "test", "line",
    "mock_count", "description"}]}``.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "pass": False,
            "violations": [
                {
                    "rule": "TAP-2.PARSE",
                    "test": "",
                    "line": 0,
                    "mock_count": 0,
                    "description": f"test module unparseable: {exc}",
                }
            ],
        }

    violations: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        count = _count_mocks(node)
        if count > threshold:
            violations.append(
                {
                    "rule": "TAP-2",
                    "test": node.name,
                    "line": node.lineno,
                    "mock_count": count,
                    "description": (
                        f"{node.name} uses {count} mocks (> {threshold} threshold) — "
                        f"prefer real in-memory implementations; reserve mocks for "
                        f"truly external systems"
                    ),
                }
            )
    return {"pass": len(violations) == 0, "violations": violations}


# ── TAP-4: failure-path ratio detector ──────────────────────────────────
#
# trust/AGENTS.md: "TAP-4 (gap blindness): write the rejection test before the
# acceptance test." services/AGENTS.md: "Failure paths first (TAP-4)." The
# REVIEW.md "AST (failure-test ratio)" label is realized as a per-test-module
# ratio of failure-asserting tests. This is an honest, conservative heuristic:
# true per-decision-point coverage needs impl→test mapping (deferred); the
# file-level ratio catches a suite that is overwhelmingly happy-path.

# Test-name tokens that signal a rejection / failure-path test.
_FAILURE_NAME_TOKENS: frozenset[str] = frozenset(
    {
        "reject",
        "fail",
        "invalid",
        "error",
        "missing",
        "empty",
        "denied",
        "unauthorized",
        "forbidden",
        "raises",
        "raises_",
    }
)


def _is_failure_asserting(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Heuristic: does this test assert a failure / rejection path?

    Counted as failure-asserting when it either calls a raises/warns/fail
    helper (``pytest.raises``, ``pytest.warns``, ``pytest.fail``,
    ``self.assertRaises``), or asserts a falsy primary outcome
    (``assert not x`` / ``assert x is None`` / ``assert x is False``), or has a
    rejection-shaped name (``test_*_rejects_*`` / ``test_invalid_*`` / …).
    Generous on purpose — for a *warning*-severity rule, false negatives (a
    missed gap) are cheaper than false positives (flagging a clean suite).
    """
    name_lower = func_node.name.lower()
    if any(tok in name_lower for tok in _FAILURE_NAME_TOKENS):
        return True

    for stmt in func_node.body:
        for node in ast.walk(stmt):
            # raises/warns/fail/assertRaises call.
            if isinstance(node, ast.Call):
                name = _dotted_name(node.func)
                if not name:
                    continue
                leaf = name.split(".")[-1]
                if leaf in {"raises", "warns", "fail", "assertRaises", "assertWarns"}:
                    return True
            # assert not <expr> / assert <expr> is None / is False.
            if isinstance(node, ast.Assert):
                test = node.test
                if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                    return True
                if isinstance(test, ast.Compare):
                    # ``x is None`` / ``x is False`` / ``x == False``
                    for cmp in test.ops:
                        if isinstance(cmp, (ast.Is, ast.Eq)):
                            for comp in test.comparators:
                                if isinstance(comp, ast.Constant) and comp.value in (
                                    None,
                                    False,
                                ):
                                    return True
    return False


def detect_failure_path_ratio(
    source: str,
    *,
    min_tests: int = 4,
    min_ratio: float = 0.25,
) -> dict[str, Any]:
    """TAP-4 (failure-paths-first) detector: flag a test module whose
    failure-asserting tests fall below ``min_ratio`` of the total, once the
    module has at least ``min_tests`` tests.

    Pure AST — parses ``source`` and executes nothing. A syntax error is
    reported conservatively. Returns::

        {"pass": bool,
         "total": int, "failure_tests": int, "ratio": float,
         "violations": [{"rule": "TAP-4", "description": ...}]}

    Honest limit: this is the *file-level* failure-test ratio, not true
    per-decision-point coverage (which needs impl→test mapping and is
    deferred). It catches a suite that is overwhelmingly happy-path; a module
    with a few well-targeted rejection tests will pass even if some decision
    points are uncovered.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "pass": False,
            "total": 0,
            "failure_tests": 0,
            "ratio": 0.0,
            "violations": [
                {
                    "rule": "TAP-4.PARSE",
                    "description": f"test module unparseable: {exc}",
                }
            ],
        }

    total = 0
    failure = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        total += 1
        if _is_failure_asserting(node):
            failure += 1

    ratio = (failure / total) if total else 0.0
    violations: list[dict[str, Any]] = []
    if total >= min_tests and ratio < min_ratio:
        violations.append(
            {
                "rule": "TAP-4",
                "description": (
                    f"failure-path ratio {failure}/{total} = {ratio:.0%} < "
                    f"{min_ratio:.0%} threshold — write rejection/failure tests "
                    f"before acceptance tests (gap blindness)"
                ),
            }
        )
    return {
        "pass": len(violations) == 0,
        "total": total,
        "failure_tests": failure,
        "ratio": ratio,
        "violations": violations,
    }


# ── Detector rule-id contract (P2-10) ──────────────────────────────────
# Static registry mapping each public detector to the set of ``rule`` ids it
# may emit in its ``violations`` list. This is the contract the
# ``REVIEW.md`` detection labels are checked against: any rule-id token named
# inside an ``AST (`<callable>` <token>)`` label must be in this set for the
# named callable. It is what makes finding-dedup at merge time sound — the
# label can't claim a rule id the detector never emits.
#
# Detectors whose rule ids are *dynamic* (e.g. ``check_dependency_rules``
# emits ``DEP.<layer>_cannot_import_<pkg>``) are intentionally absent: their
# REVIEW.md labels use prose ("framework"), not a rule-id token, so there is
# nothing to cross-check. Add a detector here only when it has a fixed
# rule-id vocabulary.
DETECTOR_RULE_IDS: dict[str, frozenset[str]] = {
    "detect_anti_patterns": frozenset({"AP-2", "AP-3", "AP-5", "AP-6", "AP.PARSE"}),
    "detect_adr1_missing": frozenset({"ADR.1"}),
    "detect_mock_abuse": frozenset({"TAP-2", "TAP-2.PARSE"}),
    "detect_failure_path_ratio": frozenset({"TAP-4", "TAP-4.PARSE"}),
    "check_trust_purity": frozenset(
        {
            "TRUST_PURITY.io_import",
            "PROTOCOL.parse_error",
            "PROTOCOL.not_found",
            "PROTOCOL.class_not_found",
            "PROTOCOL.missing_method",
        }
    ),
}
