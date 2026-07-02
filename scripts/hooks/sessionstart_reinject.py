#!/usr/bin/env python3
"""SessionStart hook — re-inject the active subtree's nested AGENTS.md guides.

Wired in ``.claude/settings.local.json`` under ``hooks.SessionStart`` (matcher
``compact``). Compaction rebuilds the context from the summary + root
``CLAUDE.md``/``AGENTS.md`` — but the **nested** per-folder ``AGENTS.md`` guides
(loaded lazily when a file in their subtree was first read) do NOT survive it.
This hook detects which guided subtrees the session is actively editing (via
``git diff`` — deterministic, no transcript parsing) and hands their guides back
via ``hookSpecificOutput.additionalContext``.

**Why SessionStart, not PostCompact:** PostCompact has *no decision control* in
the Claude Code hook schema — it cannot inject context (a
``PostCompact``/``additionalContext`` payload is rejected with "Hook JSON output
validation failed — (root): Invalid input"). SessionStart *does* accept
``additionalContext`` and exposes a ``source`` field whose ``"compact"`` value
fires precisely when a session resumes after auto/manual compaction. So we wire
under SessionStart and gate on ``source == "compact"`` — that reproduces the
post-compaction timing without re-injecting on every fresh startup/resume/clear.

Contract (HOOK-4, see scripts/hooks/AGENTS.md):
  * stdin  : JSON SessionStart payload (``source``:
             startup|resume|clear|compact). Malformed → silent exit 0 (HOOK-3).
  * gate   : only ``source == "compact"`` injects; every other source is a
             silent no-op (the lazily-loaded guides only need re-priming after
             compaction drops them).
  * stdout : ``{"hookSpecificOutput": {"hookEventName": "SessionStart",
             "additionalContext": …}}`` — advisory context, bounded ≤ ~10 KB.
             SessionStart cannot block; exit code is always 0.
  * silent : non-compact source, no uncommitted changes, or none under a guided
             subtree — the root guide is auto-reloaded by the harness, we never
             duplicate it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Payload ceiling for the injected context. Compaction exists to *shrink* the
# context; an unbounded re-inject would defeat it.
BUDGET_CHARS = 10_000

_HEADER = (
    "[sessionstart_reinject] Compaction dropped the lazily-loaded nested "
    "AGENTS.md guides for subtrees this session is editing (the root AGENTS.md "
    "is auto-reloaded; these are not):\n"
)


def _read_stdin() -> dict | None:
    """Drain the SessionStart payload. Malformed → None (HOOK-3 fail-safe)."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return None
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _changed_files() -> list[str]:
    """Working-tree files vs HEAD, including untracked. [] on any git error.

    ``git diff HEAD`` alone misses brand-new (untracked) files — exactly the
    ones a mid-feature session is editing — so untracked paths are appended
    via ``ls-files --others``.
    """

    def _run(args: list[str]) -> list[str]:
        try:
            proc = subprocess.run(
                ["git", *args],
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

    return _run(["diff", "--name-only", "HEAD"]) + _run(
        ["ls-files", "--others", "--exclude-standard"]
    )


def _guided_dirs() -> list[str]:
    """Repo-relative dirs (≤2 levels deep) that carry a nested AGENTS.md."""
    dirs: list[str] = []
    for pattern in ("*/AGENTS.md", "*/*/AGENTS.md"):
        for guide in REPO_ROOT.glob(pattern):
            rel = guide.parent.relative_to(REPO_ROOT).as_posix()
            if rel.startswith(".") or "node_modules" in rel:
                continue
            dirs.append(rel)
    return sorted(set(dirs))


def active_agents_files(changed: list[str], agents_dirs: list[str]) -> list[str]:
    """Nested AGENTS.md paths for the subtrees the changed files live in.

    Deepest matching guided dir wins per file; result is sorted + de-duplicated.
    Files under no guided dir contribute nothing (root is never re-injected).
    """
    by_depth = sorted(agents_dirs, key=lambda d: d.count("/"), reverse=True)
    hits: set[str] = set()
    for path in changed:
        for d in by_depth:
            if path.startswith(d + "/"):
                hits.add(f"{d}/AGENTS.md")
                break
    return sorted(hits)


def build_context(
    agents_files: list[str],
    read: Callable[[str], str | None],
    budget: int = BUDGET_CHARS,
) -> str:
    """Header + guide contents, bounded by *budget*.

    Guides are appended in order until the budget is hit; anything that would
    overflow degrades to a "re-read these paths" list instead of raw content.
    """
    parts: list[str] = [_HEADER]
    used = len(_HEADER)
    overflow: list[str] = []
    for path in agents_files:
        body = read(path)
        if body is None:
            overflow.append(path)
            continue
        block = f"\n--- {path} ---\n{body.strip()}\n"
        if used + len(block) > budget:
            overflow.append(path)
            continue
        parts.append(block)
        used += len(block)
    if overflow:
        parts.append(
            "\nOver the re-inject budget — re-read these before editing their "
            "subtrees: " + ", ".join(overflow)
        )
    return "".join(parts)


def render_output(context: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


def main() -> int:
    payload = _read_stdin()
    if payload is None:
        return 0  # HOOK-3: never crash or emit garbage on a bad payload.

    # Only a post-compaction start needs the nested guides re-primed; a fresh
    # startup / resume / clear either never loaded them or keeps the harness's
    # own reload path. Guard here so we don't inject on every session.
    if payload.get("source") != "compact":
        return 0

    changed = _changed_files()
    if not changed:
        return 0

    files = active_agents_files(changed, _guided_dirs())
    if not files:
        return 0

    def _read(rel: str) -> str | None:
        try:
            return (REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError:
            return None

    print(json.dumps(render_output(build_context(files, _read))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
