"""M-Phase2 swap-radius enforcement: a backend service swap must NOT touch
the adapter ring.

Per AGENT_UI_ADAPTER_SPRINTS.md M-Phase2.2: CI should parse the PR diff and
fail if ``agent_ui_adapter/**`` is modified alongside ``services/*.py``
(non-test) in the same commit range.

This test uses ``git diff --name-only`` against the merge base with the
default branch. It skips cleanly when:
  - Not inside a git repository
  - No remote ``origin`` is configured
  - The default branch (``main`` or ``master``) is not found
  - No merge-base can be computed (e.g. shallow clone)

The test only fires when BOTH conditions are true:
  1. A ``services/*.py`` file (excluding ``tests/``) was modified
  2. An ``agent_ui_adapter/**`` file (excluding ``tests/``) was modified

This is NOT a general "no co-change" rule; it specifically gates the
swap-radius claim from plan §10.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _find_default_branch() -> str | None:
    for candidate in ("origin/main", "origin/master"):
        ref = _git("rev-parse", "--verify", candidate)
        if ref:
            return candidate
    return None


def _changed_files_since_merge_base(default_branch: str) -> list[str] | None:
    merge_base = _git("merge-base", "HEAD", default_branch)
    if not merge_base:
        return None
    output = _git("diff", "--name-only", f"{merge_base}..HEAD")
    if output is None:
        return None
    return [line for line in output.splitlines() if line.strip()]


def _is_source_file(path: str) -> bool:
    return path.endswith(".py") and not path.startswith("tests/")


class TestMPhase2SwapRadius:
    def test_service_swap_does_not_touch_adapter(self) -> None:
        """If any services/*.py (non-test) changed, no agent_ui_adapter/**
        (non-test) may have changed in the same range."""
        default_branch = _find_default_branch()
        if default_branch is None:
            pytest.skip("no origin/main or origin/master found")

        changed = _changed_files_since_merge_base(default_branch)
        if changed is None:
            pytest.skip("could not compute merge-base (shallow clone?)")

        service_changes = [
            p for p in changed
            if p.startswith("services/") and _is_source_file(p)
        ]
        adapter_changes = [
            p for p in changed
            if p.startswith("agent_ui_adapter/") and _is_source_file(p)
        ]

        if not service_changes:
            pytest.skip("no services/*.py source changes in this range")

        assert not adapter_changes, (
            "M-Phase2 swap-radius violation: backend service swap must not "
            "touch the adapter ring.\n"
            f"  Service changes: {service_changes}\n"
            f"  Adapter changes: {adapter_changes}\n"
            "If this is intentional (not a backend swap), this test can be "
            "skipped with -k 'not swap_radius'."
        )
