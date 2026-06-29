#!/usr/bin/env python3
"""PostToolUse hook that BLOCKS the edit — violates HOOK-1.

HOOK-1: a PostToolUse hook must NEVER block the edit (it may observe, log, or
format, but the edit stands). This hook emits a "block" decision and exits
non-zero, which would reject the user's edit.
"""

import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    _ = payload  # unused
    # HOOK-1 violation: blocking decision from a PostToolUse hook.
    print(json.dumps({"decision": "block", "reason": "edit rejected by guard"}))
    return 2  # non-zero exit + block decision


if __name__ == "__main__":
    sys.exit(main())
