"""Architecture gate: the ADR.1 ratchet (harness v2 plan, item 2.1).

The mechanical sensor for the ADR.1 ratchet in AGENTS.md (Decision records). When
the working branch touches an ``⚠️ Ask first`` trigger — a `pyproject.toml`
change, a `trust/models.py` change, a new `orchestration/react_loop.py` node, or a
newly-added `services/<name>/__init__.py` (a new horizontal service) — it must
ship a new file under `docs/adr/`, OR carry an explicit `# ADR-OK` waiver in the
commit messages of the range. Otherwise the structural decision lands with its
*why* uncaptured (the comprehension-debt the ratchet exists to prevent).

The detection logic is the pure, unit-tested
``utils.code_analysis.detect_adr1_missing`` (already shipped by Track A). This
module is only the git glue that feeds it the diff facts — mirroring
``test_no_test_weakening`` so the two share one idiom.

Verify-first note (plan 2.1): the Stop-hook payload was considered as the trigger
source, but a git-diff arch-test is version-independent, runs in CI like the other
trusted gates, and a hook cannot capture the typed human answer the gate wants
anyway (the honest limit). So this is the chosen mechanism; a Stop hook would only
be an advisory echo of it.

Skips cleanly when not in a git repo, no `origin/main`/`origin/master`, or no
merge-base (shallow clone) — never a false failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from utils.code_analysis import detect_adr1_missing

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# A commit-message token that explicitly waives the ratchet for the range (e.g. a
# dependency bump that genuinely needs no design record). Kept greppable.
_WAIVER_TOKEN = "ADR-OK"


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


def _changed_files(merge_base: str) -> list[str]:
    out = _git("diff", "--name-only", f"{merge_base}..HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()] if out else []


def _added_files(merge_base: str) -> list[str]:
    out = _git("diff", "--name-only", "--diff-filter=A", f"{merge_base}..HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()] if out else []


def _range_messages(merge_base: str) -> str:
    out = _git("log", "--format=%B", f"{merge_base}..HEAD")
    return out or ""


class TestAdrRatchet:
    def test_ask_first_trigger_has_an_adr_or_waiver(self):
        default_branch = _find_default_branch()
        if default_branch is None:
            pytest.skip("no origin/main or origin/master found")

        merge_base_out = _git("merge-base", "HEAD", default_branch)
        if not merge_base_out:
            pytest.skip("could not compute merge-base (shallow clone?)")
        merge_base = merge_base_out.strip()

        changed = _changed_files(merge_base)
        if not changed:
            pytest.skip("no changes in this range")

        # An explicit waiver in any commit message of the range releases the gate.
        if _WAIVER_TOKEN in _range_messages(merge_base):
            pytest.skip(f"{_WAIVER_TOKEN} waiver present in the range")

        result = detect_adr1_missing(changed, added_files=_added_files(merge_base))

        assert result["pass"], (
            "ADR.1 ratchet: an ⚠️ Ask-first trigger changed without a new docs/adr/ "
            "file. File an ADR (copy docs/adr/0000-template.md) and register it in "
            f"index.md + log.md, or add an '{_WAIVER_TOKEN}: <reason>' line to a "
            "commit message in the range. Triggers: "
            + ", ".join(result.get("triggers", []))
        )
