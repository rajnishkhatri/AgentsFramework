"""Architecture gate: the working branch must not silently weaken the test suite.

The mechanical form of the **G8 (test-mass-rewrite) gate** in AGENTS.md. For every
``tests/**.py`` file changed versus the merge-base with the default branch, compare
the base version against the working tree and fail when a change either:

  * removes a ``def test_*`` (a test disappears), or
  * newly marks a test ``@pytest.mark.skip`` / ``skipif`` / ``xfail`` without a
    justification token (``G8-OK``, ``ADR-…``, ``flaky-tracked:``, ``live_llm``,
    ``env-gated:``) in its reason.

The detection core is the pure, unit-tested
``utils.code_analysis.detect_test_weakening`` — this module is only the git glue
that resolves old/new content, mirroring ``test_mphase2_swap_radius`` so the two
share one diffing idiom.

Skips cleanly (never false-fails) when: not in a git repo, no ``origin/main`` /
``origin/master``, the merge-base can't be computed (shallow clone), or no test
files changed in the range. A deleted-whole-file change is reported as removed
tests; a renamed file shows as old-deleted + new-added (the added side has no base,
so its tests are 'new', not 'removed' — rename is not a weakening).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from utils.code_analysis import detect_test_weakening

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _find_default_branch() -> str | None:
    for candidate in ("origin/main", "origin/master"):
        if _git("rev-parse", "--verify", candidate) is not None:
            return candidate
    return None


def _changed_test_files(merge_base: str) -> list[str]:
    out = _git("diff", "--name-only", f"{merge_base}..HEAD")
    if out is None:
        return []
    return [
        line.strip()
        for line in out.splitlines()
        if line.strip().startswith("tests/") and line.strip().endswith(".py")
    ]


def _base_content(merge_base: str, path: str) -> str | None:
    """File content at the merge base, or None if it did not exist there."""
    return _git("show", f"{merge_base}:{path}")


def _working_content(path: str) -> str | None:
    fp = _REPO_ROOT / path
    if not fp.exists():
        return None
    return fp.read_text()


class TestNoTestWeakening:
    def test_no_unjustified_test_weakening_vs_merge_base(self):
        default_branch = _find_default_branch()
        if default_branch is None:
            pytest.skip("no origin/main or origin/master found")

        merge_base_out = _git("merge-base", "HEAD", default_branch)
        if not merge_base_out:
            pytest.skip("could not compute merge-base (shallow clone?)")
        merge_base = merge_base_out.strip()

        changed = _changed_test_files(merge_base)
        if not changed:
            pytest.skip("no tests/**.py changes in this range")

        violations: list[str] = []
        for path in changed:
            old = _base_content(merge_base, path)
            new = _working_content(path)
            if old is None:
                # Added file (or rename target): no base to weaken. Skip.
                continue
            # Whole file deleted (new is None) ⇒ compare against an empty module,
            # so every base test reads as removed.
            result = detect_test_weakening(old, new if new is not None else "")
            for v in result["violations"]:
                violations.append(f"{path}: [{v['rule']}] {v['description']}")

        assert violations == [], (
            "Test suite weakened versus the merge base (G8). Each line is a removed "
            "test or a newly-skipped/xfailed test without a justification token "
            "(G8-OK / ADR-… / flaky-tracked: / live_llm / env-gated:). If the change "
            "is legitimate, add the token to the skip reason or restore the test:\n"
            + "\n".join(violations)
        )
