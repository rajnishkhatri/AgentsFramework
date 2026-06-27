#!/usr/bin/env python3
"""Cursor `beforeShellExecution` hook — block dangerous shell commands.

Cursor parity for the Claude Code ``pre_bash_guard.py`` hook (Track A). Cursor
expects a JSON decision on stdout: ``{"permission": "allow"}`` or
``{"permission": "deny", "userMessage": "..."}``. Combined with
``"failClosed": true`` in ``.cursor/hooks.json``, a crash/timeout denies rather
than silently allows (Cursor hooks fail OPEN by default).

The deny-list is kept identical to ``pre_bash_guard.py`` by importing it, so the
two tools never drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pre_bash_guard import DANGEROUS  # noqa: E402  (path set above)


def _command(payload: dict) -> str | None:
    return (
        payload.get("command")
        or (payload.get("tool_input") or {}).get("command")
        or payload.get("shellCommand")
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Fail closed: deny on a payload we can't parse.
        print(
            json.dumps({"permission": "deny", "userMessage": "unparseable hook input"})
        )
        return 0

    command = _command(payload)
    if not command:
        print(json.dumps({"permission": "allow"}))
        return 0

    for pattern, reason in DANGEROUS:
        if pattern.search(command):
            print(json.dumps({"permission": "deny", "userMessage": reason}))
            return 0

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
