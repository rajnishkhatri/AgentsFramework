"""Deterministic tool-dispatch table for the Frontend Reviewer runner.

Maps the Section 5 tool names from
``prompts/codeReviewer/frontend/system_prompt.j2`` to a Python callable
that shells out to the backing TS script under ``frontend/scripts/`` (or
to ``pytest`` / ``vitest`` for the few tools whose contract IS the test).

The dispatch is consumed by:

- ``--rules-only`` mode (runs every applicable tool against the file list
  with no LLM in the loop -- a CI fast-check), and
- the future LiteLLM tool-calling handler that lets the LLM invoke any
  tool by name.

Each handler returns the raw JSON dict the corresponding TS script emits
on stdout, plus the process exit code so the runner can preserve the
script's PASS/FAIL semantics. Failures and missing scripts surface as
``{"pass": False, "error": "..."}`` -- callers never see a Python
exception.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger("code_reviewer.frontend.tools")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_ROOT = REPO_ROOT / "frontend"
SCRIPTS_DIR = FRONTEND_ROOT / "scripts"

# Mapping rule from FRONTEND_REVIEWER_PROMPT §5: tool name -> backing
# `frontend/scripts/<name>.ts` script. The list intentionally excludes
# tools whose contract is "the test is the tool" (run_pytest_*, etc.) --
# those are dispatched separately via ``run_pytest_node``.
TS_SCRIPT_MAP: Mapping[str, str] = {
    "check_csp_strict": "check_csp_strict.ts",
    "check_iframe_sandbox": "check_iframe_sandbox.ts",
    "check_composer_keyboard": "check_composer_keyboard.ts",
    "check_sprint_story": "check_sprint_story.ts",
    "check_secrets_in_public_env": "check_secrets_in_public_env.ts",
    "check_jwt_storage": "check_jwt_storage.ts",
    "check_axe_a11y": "check_axe_a11y.ts",
    "check_bundle_budget": "check_bundle_budget.ts",
}


def _have_tsx() -> bool:
    """Return True when the local `tsx` binary is on PATH (or in node_modules)."""
    if shutil.which("tsx") is not None:
        return True
    local = FRONTEND_ROOT / "node_modules" / ".bin" / "tsx"
    return local.exists()


def _tsx_command(script: str, *args: str) -> list[str]:
    """Build the npx-or-local-bin command line for a frontend/scripts/ script."""
    bin_path = FRONTEND_ROOT / "node_modules" / ".bin" / "tsx"
    if bin_path.exists():
        return [str(bin_path), str(SCRIPTS_DIR / script), *args]
    return ["npx", "tsx", str(SCRIPTS_DIR / script), *args]


def run_ts_script(name: str, *args: str, timeout_s: int = 60) -> dict[str, Any]:
    """Invoke a `frontend/scripts/<name>.ts` script and return its parsed JSON.

    Always returns a dict with at least ``pass`` and ``exit_code`` keys.
    Never raises -- transport errors surface as
    ``{"pass": False, "error": "..."}``.

    @param name      Script name (without the `.ts` extension), e.g.
                     ``check_csp_strict``.
    @param args      Positional CLI arguments forwarded to the script.
    @param timeout_s Hard timeout for the subprocess.
    """
    script = TS_SCRIPT_MAP.get(name)
    if script is None:
        return {"pass": False, "exit_code": 2, "error": f"unknown TS tool: {name}"}
    if not (SCRIPTS_DIR / script).exists():
        return {
            "pass": False,
            "exit_code": 2,
            "error": f"script not found: frontend/scripts/{script}",
        }
    if not _have_tsx():
        return {
            "pass": False,
            "exit_code": 2,
            "error": "tsx is not installed; run `cd frontend && npm install`",
        }

    cmd = _tsx_command(script, *args)
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "pass": False,
            "exit_code": 2,
            "error": f"TS tool {name} timed out after {timeout_s}s",
        }
    except (OSError, FileNotFoundError) as exc:
        return {"pass": False, "exit_code": 2, "error": str(exc)}

    parsed: dict[str, Any]
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return {
            "pass": False,
            "exit_code": proc.returncode,
            "error": "TS tool emitted invalid JSON",
            "stdout": proc.stdout[:2000],
            "stderr": proc.stderr[:2000],
        }
    parsed.setdefault("pass", proc.returncode == 0)
    parsed["exit_code"] = proc.returncode
    return parsed


def run_pytest_node(node: str, *, timeout_s: int = 120) -> dict[str, Any]:
    """Run a single pytest node id and return ``{pass, exit_code, output}``.

    Used by the FD9 / FD10 / FD11 hypotheses whose authoritative tool IS
    the architecture / infra pytest module.
    """
    cmd = ["pytest", node, "-q"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"pass": False, "exit_code": 2, "output": f"pytest timed out: {node}"}
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return {"pass": proc.returncode == 0, "exit_code": proc.returncode, "output": output[:8000]}


# ── Helpers for `--rules-only` mode ─────────────────────────────────


def _is_middleware_file(rel: str) -> bool:
    return rel.endswith("middleware.ts") and "/lib/" not in rel


def _is_composer_file(rel: str) -> bool:
    return rel.endswith("Composer.tsx") or rel.endswith("composer.tsx")


def _is_env_file(rel: str) -> bool:
    name = Path(rel).name
    return name.startswith(".env") or name == "next.config.ts"


def _is_tsx_file(rel: str) -> bool:
    return rel.endswith(".tsx")


def _is_ts_file(rel: str) -> bool:
    return rel.endswith(".ts") or rel.endswith(".tsx")


def applicable_tools(filepath: str) -> list[tuple[str, list[str]]]:
    """Return the (tool_name, args) list that should run against `filepath`.

    Used by ``--rules-only`` to decide which deterministic tools to fire
    for each file in the review set.

    The mapping mirrors the deterministic-first section of the Frontend
    Reviewer system prompt: each file's classification picks the union of
    rule families it can violate. Missing classifications return [] so the
    runner can still report unmatched files in `validation_log[]`.
    """
    rel = filepath
    out: list[tuple[str, list[str]]] = []
    if _is_middleware_file(rel):
        out.append(("check_csp_strict", [filepath]))
    if _is_composer_file(rel):
        out.append(("check_composer_keyboard", [filepath]))
    if _is_tsx_file(rel):
        out.append(("check_iframe_sandbox", [filepath]))
    if _is_env_file(rel):
        out.append(("check_secrets_in_public_env", [filepath]))
    if _is_ts_file(rel):
        out.append(("check_jwt_storage", [filepath]))
    return out


# ── Tool catalogue used by the (future) LLM tool-calling wiring ─────


def tool_function_specs() -> list[dict[str, Any]]:
    """Return LiteLLM-compatible tool function specs for every TS script.

    The runner does not invoke the LLM today (tracked as an open gap in
    the module docstring) but emitting the spec block here keeps the
    later integration narrow -- when the LLM tool-calling loop lands the
    handler simply maps each function name to ``run_ts_script(name, ...)``.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "check_csp_strict",
                "description": (
                    "Parse the CSP header from a Next.js middleware file and "
                    "assert FD3.CSP1/CSP2 + the hardening trio (object-src "
                    "'none', base-uri 'self', frame-ancestors 'none')."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "middleware_filepath": {"type": "string"},
                    },
                    "required": ["middleware_filepath"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_iframe_sandbox",
                "description": (
                    "JSX walk for every <iframe>; assert SBX1 sandbox present "
                    "and SBX2 token list is allow-scripts only (no allow-same-"
                    "origin / allow-top-navigation / allow-forms / etc.)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"filepath": {"type": "string"}},
                    "required": ["filepath"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_composer_keyboard",
                "description": (
                    "Composer-style component checker: U_KBD, U_IME, "
                    "U_AUTOSIZE, U_LBL, U_FOCUS_NO_STEAL."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"filepath": {"type": "string"}},
                    "required": ["filepath"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_sprint_story",
                "description": (
                    "Re-derive a single Sprint Board story's PASS/PARTIAL/FAIL "
                    "by checking key_files exist and dispatching the "
                    "acceptance_signal shell command."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"story_id": {"type": "string"}},
                    "required": ["story_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_secrets_in_public_env",
                "description": (
                    "Flag NEXT_PUBLIC_* names matching *KEY*, *SECRET*, *TOKEN*, "
                    "*PRIVATE*, *API*, *CREDENTIAL* and raw secret-shaped "
                    "default values."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"env_filepath": {"type": "string"}},
                    "required": ["env_filepath"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_jwt_storage",
                "description": (
                    "AST scan for localStorage/sessionStorage setItem with "
                    "auth-shaped key or value (token/jwt/access/session/"
                    "bearer/auth)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"filepath": {"type": "string"}},
                    "required": ["filepath"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_axe_a11y",
                "description": (
                    "STUB. Returns skipped:true today; emits violation list "
                    "when @axe-core/playwright + .storybook/ ship."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"target": {"type": "string"}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_bundle_budget",
                "description": (
                    "STUB. Returns skipped:true today; compares First Load JS "
                    "against frontend/.bundle-baseline.json when both ship."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"route": {"type": "string"}},
                    "required": [],
                },
            },
        },
    ]


# Tool handler dispatch (used by the LLM tool-calling loop when it lands).
ToolHandler = Callable[..., dict[str, Any]]
TOOL_HANDLERS: Mapping[str, ToolHandler] = {
    name: (lambda _name=name, **kw: run_ts_script(_name, *_pos_args(_name, kw)))
    for name in TS_SCRIPT_MAP
}


def _pos_args(name: str, kwargs: dict[str, Any]) -> list[str]:
    """Map a tool's structured kwargs to the positional CLI args its TS twin expects.

    Each TS script takes a single positional argument -- this helper picks
    it out of ``kwargs`` by the documented parameter name in
    :func:`tool_function_specs`. Unknown tools fall back to whatever
    string args the caller provided in declaration order.
    """
    schema_lookup = {
        "check_csp_strict": ("middleware_filepath",),
        "check_iframe_sandbox": ("filepath",),
        "check_composer_keyboard": ("filepath",),
        "check_sprint_story": ("story_id",),
        "check_secrets_in_public_env": ("env_filepath",),
        "check_jwt_storage": ("filepath",),
        "check_axe_a11y": ("target",),
        "check_bundle_budget": ("route",),
    }
    keys = schema_lookup.get(name, tuple(kwargs.keys()))
    return [str(kwargs[k]) for k in keys if k in kwargs and kwargs[k] is not None]


__all__ = [
    "REPO_ROOT",
    "FRONTEND_ROOT",
    "SCRIPTS_DIR",
    "TS_SCRIPT_MAP",
    "TOOL_HANDLERS",
    "applicable_tools",
    "run_ts_script",
    "run_pytest_node",
    "tool_function_specs",
]
