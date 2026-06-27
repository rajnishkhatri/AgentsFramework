#!/usr/bin/env python3
"""PostToolUse hook — auto-format + lint Python files the agent just edited.

Wired in ``.claude/settings.local.json`` under ``hooks.PostToolUse`` with matcher
``Edit|Write``. Track A of the agentic-engineering harness adoption
(``docs/plan/agentic_engineering_harness_adoption.plan.md``).

Contract (Claude Code hooks):
  * stdin  : JSON describing the tool call; we read ``tool_input.file_path``.
  * exit 0 : nothing to do / clean — silent, does not interrupt the agent.
  * exit 2 : residual lint printed to stderr is fed back to the agent so it
             self-corrects. PostToolUse CANNOT block the write (file is already
             on disk) — exit 2 here is feedback, not a block. This is the
             "never block Edit/Write mid-reasoning" rule: we clean up + report.

Only ``*.py`` files are touched; everything else is a no-op. Uses the repo
virtualenv ruff (``.venv/bin/ruff``) per the Makefile interpreter convention —
a Homebrew/conda tool on PATH is not guaranteed to resolve this project's deps.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUFF = REPO_ROOT / ".venv" / "bin" / "ruff"


def _read_file_path() -> str | None:
    """Extract the edited file path from the hook's stdin JSON payload."""
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Malformed payload: fail safe (do nothing, don't interrupt the agent).
        return None
    tool_input = payload.get("tool_input") or {}
    return tool_input.get("file_path")


def _run_ruff(args: list[str], target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(RUFF), *args, target],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def main() -> int:
    file_path = _read_file_path()
    if not file_path:
        return 0

    target = Path(file_path)
    # Only act on Python source files that still exist on disk.
    if target.suffix != ".py" or not target.exists():
        return 0

    if not RUFF.exists():
        # ruff not installed in the venv — don't punish the agent for an env gap.
        print(
            f"[post_edit_ruff] {RUFF} not found; skipping format/lint. "
            'Run `pip install -e ".[dev]"` to enable the hook.',
            file=sys.stderr,
        )
        return 0

    # 1) Auto-format (idempotent, never fails on style).
    _run_ruff(["format"], str(target))
    # 2) Auto-fix what ruff can fix safely.
    _run_ruff(["check", "--fix"], str(target))
    # 3) Re-check for anything still unfixable and surface it to the agent.
    residual = _run_ruff(["check"], str(target))

    if residual.returncode != 0:
        message = (residual.stdout or "") + (residual.stderr or "")
        print(
            "[post_edit_ruff] Auto-formatted and auto-fixed "
            f"{target}, but these lint issues remain — please fix:\n{message}",
            file=sys.stderr,
        )
        return 2  # feed residual lint back to the agent (does not block).

    return 0


if __name__ == "__main__":
    sys.exit(main())
