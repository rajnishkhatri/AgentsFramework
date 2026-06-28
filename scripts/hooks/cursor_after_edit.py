#!/usr/bin/env python3
"""Cursor `afterFileEdit` hook — format + lint Python the agent just edited.

Cursor parity for the Claude Code ``post_edit_ruff.py`` hook (Track A). Cursor's
hook protocol differs from Claude Code's: input is JSON on stdin, and Cursor
reads any JSON object printed to stdout (no exit-code semantics). For
``afterFileEdit`` there is no block decision — we format/fix in place and emit
the residual lint as a user-visible message.

Input shape (Cursor): ``{"file_path": "...", ...}`` (key name has varied across
betas; we also accept ``filePath``/``tool_input.file_path`` defensively).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUFF = REPO_ROOT / ".venv" / "bin" / "ruff"


def _file_path(payload: dict) -> str | None:
    return (
        payload.get("file_path")
        or payload.get("filePath")
        or (payload.get("tool_input") or {}).get("file_path")
    )


def _ruff(args: list[str], target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(RUFF), *args, target], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(json.dumps({}))
        return 0

    target_str = _file_path(payload)
    if not target_str:
        print(json.dumps({}))
        return 0

    target = Path(target_str)
    if target.suffix != ".py" or not target.exists() or not RUFF.exists():
        print(json.dumps({}))
        return 0

    _ruff(["format"], str(target))
    _ruff(["check", "--fix"], str(target))
    residual = _ruff(["check"], str(target))

    if residual.returncode != 0:
        message = (residual.stdout or "") + (residual.stderr or "")
        print(json.dumps({"userMessage": f"ruff lint issues remain:\n{message}"}))
    else:
        print(json.dumps({}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
