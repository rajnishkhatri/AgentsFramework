#!/usr/bin/env python3
"""PreToolUse hook — block a small, explicit set of dangerous Bash commands.

Wired in ``.claude/settings.local.json`` under ``hooks.PreToolUse`` with matcher
``Bash``. Track A of the agentic-engineering harness adoption
(``docs/plan/agentic_engineering_harness_adoption.plan.md``).

Contract (Claude Code hooks):
  * stdin  : JSON describing the tool call; we read ``tool_input.command``.
  * exit 0 : allow the command (silent).
  * exit 2 : BLOCK the command; stderr is returned to the agent as the reason.

Scope — deliberately THIN. This is a last-resort safety net for irreversible /
high-blast-radius commands the AGENTS.md already forbids, NOT a general command
policy:
  * pushing to the protected ``main`` branch (AGENTS.md: "Never push to main"),
  * recursive force-deletes of broad paths (``rm -rf`` near repo root / home),
  * reading or writing ``.env`` files (AGENTS.md: "Never commit secrets / .env").

This intentionally does NOT duplicate the severity-graded shell-approval HITL
classifier (commit d5d68d9). The two are separate by design: that classifier is
the rich approve/ask/deny policy; this hook is a tiny deterministic backstop. If
this deny-list grows, reconsider folding it into the classifier instead.
"""

from __future__ import annotations

import json
import re
import sys

# (compiled pattern, human-readable reason). Keep this list short and obvious.
DANGEROUS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bgit\s+push\b.*\b(origin\s+)?main\b"),
        "Never push to main. Open a PR from a feature branch instead "
        "(AGENTS.md guardrail).",
    ),
    (
        re.compile(r"\bgit\s+push\b.*\borigin\b.*\bHEAD:main\b"),
        "Never push to main (HEAD:main form). Open a PR instead.",
    ),
    (
        # rm -rf / -fr targeting repo root ('.', './', '*') or a home/root path.
        re.compile(r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\b\s*(\.|\./|\*|/|~)"),
        "Refusing 'rm -rf' on a broad path (repo root, home, or '*'). "
        "Delete specific files explicitly instead.",
    ),
    (
        # Any read/write/cat/edit touching a .env file (but not .env.example).
        re.compile(r"(?<![\w.])\.env(?!\.example)(\.\w+)?\b"),
        "Refusing to read/write a .env file — secrets must not flow through "
        "the agent (AGENTS.md). Use .env.example for shareable templates.",
    ),
]


def _read_command() -> str | None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    tool_input = payload.get("tool_input") or {}
    return tool_input.get("command")


def main() -> int:
    command = _read_command()
    if not command:
        return 0  # nothing to inspect — allow.

    for pattern, reason in DANGEROUS:
        if pattern.search(command):
            print(f"[pre_bash_guard] BLOCKED: {reason}", file=sys.stderr)
            return 2  # block the tool call; stderr becomes the agent's reason.

    return 0


if __name__ == "__main__":
    sys.exit(main())
