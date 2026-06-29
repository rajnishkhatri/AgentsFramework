#!/usr/bin/env python3
"""Clean PreToolUse safety-only hook — thin, fail-safe, never blocks the edit.

HOOK-1 respected (this is PreToolUse, not PostToolUse; it never blocks edits).
HOOK-2 respected (safety-only, thin). HOOK-3 respected (fail-safe on malformed
input: a parse error exits 0 with a no-op, never a crash).
"""

import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        # HOOK-3: fail safe — do not crash the tool flow on malformed input.
        return 0

    command = str(payload.get("command", ""))
    # Safety-only: refuse to run a destructive shell pattern; surface as a
    # non-blocking note (the edit itself is never blocked by a PreToolUse hook
    # in this repo's model).
    if " rm -rf /" in command:
        print(json.dumps({"decision": "note", "reason": "destructive pattern"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
