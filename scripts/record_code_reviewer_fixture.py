#!/usr/bin/env python3
"""One-off helper: record a real ReviewReport for the L3 fixture.

Runs ``meta.code_reviewer --llm`` against ``trust/enums.py`` and writes
the resulting JSON to ``tests/fixtures/code_reviewer/review_response.json``.

Requires ``OPENAI_API_KEY`` or ``LITELLM_API_KEY`` in the environment.
NOT invoked by CI -- intended for human use when refreshing the recording
for STORY-408's L3 obligation.

Usage::

    python scripts/record_code_reviewer_fixture.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_FILE = REPO_ROOT / "trust" / "enums.py"
OUTPUT_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "code_reviewer" / "review_response.json"
)


def main() -> int:
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("LITELLM_API_KEY")):
        print(
            "ERROR: set OPENAI_API_KEY or LITELLM_API_KEY before recording.",
            file=sys.stderr,
        )
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "meta.code_reviewer",
        "--llm",
        "--files",
        str(TARGET_FILE),
        "--output",
        str(OUTPUT_PATH),
    ]
    print("Running:", " ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if completed.returncode in (0, 1, 2):
        print(f"Recording written to {OUTPUT_PATH}")
        print("Inspect, redact secrets if any, then commit.")
        return 0
    print(
        f"meta.code_reviewer exited with {completed.returncode}; no recording saved.",
        file=sys.stderr,
    )
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
