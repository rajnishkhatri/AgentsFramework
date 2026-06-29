#!/usr/bin/env python3
"""Stop hook — advise-only ADR.1 reminder when the turn ends on an Ask-first seam.

Wired in ``.claude/settings.local.json`` under ``hooks.Stop``. Complements the
merge-time ADR ratchet (``tests/architecture/test_adr_ratchet.py``): that catches
a missing ADR at merge; this reminds the author *mid-session* before the work
hardens. It is a sensor, not a gate.

Contract (Claude Code hooks; see scripts/hooks/AGENTS.md):
  * stdin  : JSON describing the Stop event (we don't need any field, but we
             read it so a malformed payload is a clean no-op — HOOK-3).
  * exit 0 : nothing to flag / clean — silent, does not interrupt the agent.
  * exit 2 : advisory text on stderr is fed back to the agent. This is a
             *reminder*, never a block — Claude Code hooks cannot capture a typed
             human gate answer (the honest limit in docs/adr/GATES.md), so the
             ADR gate stays convention + PR-review. We only surface the trigger.

Cite-don't-copy: the ⚠️ Ask-first trigger set is NOT restated here — we reuse the
single deterministic detector (``utils.code_analysis.detect_adr1_missing``) that
the arch-test ratchet and the v3 reviewer already share. The advisory points at
the GATES.md preamble and the ADR template; it never paraphrases the rules.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_stdin() -> dict | None:
    """Drain the Stop payload. Malformed/empty → None (HOOK-3 fail-safe)."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return None
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def _changed_files() -> tuple[list[str], list[str]]:
    """``(changed, added)`` working-tree files vs HEAD. ([], []) on any git error.

    Mirrors the diff shape of ``meta.code_reviewer._git_diff_files`` but stays
    self-contained (no import of the reviewer module) so the hook is cheap and
    has no heavy dependency to load on every turn end.
    """

    def _run(extra: list[str]) -> list[str]:
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-only", *extra, "HEAD"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if proc.returncode != 0:
            return []
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]

    return _run([]), _run(["--diff-filter=A"])


def main() -> int:
    payload = _read_stdin()
    if payload is None:
        return 0  # HOOK-3: never crash/block on a bad payload.

    changed, added = _changed_files()
    if not changed:
        return 0  # nothing uncommitted to evaluate.

    # Reuse the shared deterministic detector — never re-implement the trigger
    # list. Import lazily so a clean turn pays nothing.
    try:
        from utils.code_analysis import detect_adr1_missing
    except Exception:
        # Env gap (package not importable) → no-op note, not a punishment.
        print(
            "[stop_adr_reminder] could not import utils.code_analysis; "
            'skipping ADR reminder. Run `pip install -e ".[dev]"`.',
            file=sys.stderr,
        )
        return 0

    result = detect_adr1_missing(changed, added_files=added)
    if result.get("pass", True):
        return 0

    triggers = ", ".join(result.get("triggers") or [])
    print(
        "[stop_adr_reminder] ⚠️ Ask-first / architecture seam touched with no new "
        f"docs/adr/ file: {triggers}\n"
        "Before this hardens, work the comprehension preamble in "
        "docs/adr/GATES.md (G1/G7) and, if the change is load-bearing, file an ADR "
        "(copy docs/adr/0000-template.md) + update docs/adr/index.md and log.md. "
        "This is a reminder, not a block — the merge-time ratchet "
        "(tests/architecture/test_adr_ratchet.py) is the hard gate.",
        file=sys.stderr,
    )
    return 2  # advisory feedback to the agent (does not block).


if __name__ == "__main__":
    sys.exit(main())
