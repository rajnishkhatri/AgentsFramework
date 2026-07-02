#!/usr/bin/env python3
"""SessionStart hook: nudge the model to compact MEMORY.md when it's over budget.

Wired as a `SessionStart` command hook (see references/auto_trigger_hook.md), this runs
at the start of every session. If the project's MEMORY.md exceeds THRESHOLD_KB it prints
a short nudge to stdout — SessionStart forwards stdout to the model as additionalContext,
so the model sees it and can invoke the memory-compaction skill. On a healthy project it
prints nothing and exits 0, staying invisible.

A hook cannot run a skill itself; it can only surface context. That's intentional —
compaction needs judgment (which lever, whether to prune), so the model should do it.

Usage (also runnable by hand to test):
    python3 session_start_check.py [MEMORY_DIR]
"""

from __future__ import annotations

import os
import sys

THRESHOLD_KB = 15  # intervene-early line; harness hard limit is ~24.4 KB


def resolve_memory_dir(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    encoded = project.replace("/", "-")
    return os.path.join(
        os.path.expanduser("~"), ".claude", "projects", encoded, "memory"
    )


def main() -> int:
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    memory_md = os.path.join(resolve_memory_dir(explicit), "MEMORY.md")
    try:
        size_kb = os.path.getsize(memory_md) / 1024
    except OSError:
        return 0  # no memory index yet — nothing to do, stay silent
    if size_kb > THRESHOLD_KB:
        print(
            f"[memory-compaction] MEMORY.md is {size_kb:.1f} KB, over the {THRESHOLD_KB} KB "
            f"budget. The always-loaded memory index is large and risks being truncated "
            f"(which silently hides memories). Consider running the memory-compaction skill "
            f"to re-hook it down to ≤12 KB before continuing."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
