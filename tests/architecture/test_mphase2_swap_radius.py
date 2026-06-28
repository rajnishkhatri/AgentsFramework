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


def _ruff_bin() -> str | None:
    """Locate a ruff to run the format filter with, or None if none is found.

    Prefer the repo-pinned ``.venv`` ruff; fall back to a ``ruff`` on PATH (review
    #5 — a fresh CI checkout installs ruff via pre-commit's own env or a global
    install, not necessarily ``.venv``, and without this the format filter would be
    bypassed and the gate would fire on the very reformat it exists to exempt)."""
    import shutil

    candidate = _REPO_ROOT / ".venv" / "bin" / "ruff"
    if candidate.exists():
        return str(candidate)
    return shutil.which("ruff")


def _repo_root_writable() -> bool:
    """True iff a tempfile can be created in _REPO_ROOT (the discriminator and its
    test helper both host their ruff-config-resolving tempfile there). A read-only
    checkout (some hardened CI runners) makes this False; the gate stays
    conservative-fire and the discriminator unit tests skip rather than false-pass."""
    import tempfile

    try:
        with tempfile.NamedTemporaryFile("w", dir=_REPO_ROOT, delete=True):
            return True
    except OSError:
        return False


def _reformatted_matches(old_text: str, new_text: str) -> bool:
    """True iff ruff-reformatting ``old_text`` reproduces ``new_text`` exactly.

    The discriminator core, factored out of git glue so it is directly unit-tested
    (review #3 — this is the logic that decides whether the swap-radius gate fires,
    and a silent inversion here would stop the gate firing on a real swap). Runs
    the repo's ruff (``format`` + plain safe ``--fix``) on the OLD text and
    compares to the NEW text. Equal ⇒ the only change WAS the reformat (``git diff
    -w`` is insufficient: removing an unused import changes non-whitespace tokens).

    Returns ``False`` (conservative — keep the gate firing) when ruff is
    unavailable or errors: never silently classify a possible real swap as
    format-only.
    """
    ruff = _ruff_bin()
    if ruff is None:
        return False

    import tempfile

    # The tempfile lives in _REPO_ROOT (not tmp_path) so ruff resolves the repo's
    # pyproject.toml ruff config by walking up from the file's path -- a tempfile
    # in /tmp would inherit ruff's defaults, NOT the repo's fix-set, and the
    # discriminator would no longer reproduce the baseline's reformat. The
    # trade-off: a read-only repo checkout (some hardened CI runners) can't host
    # the tempfile; we catch OSError and return False (conservative -- keep the
    # gate firing on every change rather than silently exempting reformats the
    # discriminator couldn't actually check).
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, dir=_REPO_ROOT
        ) as fh:
            fh.write(old_text)
            tmp = Path(fh.name)
    except OSError:
        return False
    try:
        subprocess.run(
            [ruff, "format", "-q", str(tmp)],
            capture_output=True,
            cwd=_REPO_ROOT,
            timeout=30,
        )
        # Plain --fix (no --select): reproduce the SAME safe-fix families the repo
        # baseline applied (I import-sort, UP pyupgrade, F, E, ...), per the repo
        # ruff config. A narrower --select F,E (review #4) would not reproduce an
        # I/UP-only reformat, so a pure reformat in those families would wrongly
        # read as substantive and fire the gate.
        subprocess.run(
            [ruff, "check", "-q", "--fix", str(tmp)],
            capture_output=True,
            cwd=_REPO_ROOT,
            timeout=30,
        )
        reformatted_old = tmp.read_text()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    finally:
        tmp.unlink(missing_ok=True)

    return reformatted_old == new_text


def _has_substantive_change(default_branch: str, path: str) -> bool:
    """True iff ``path``'s change vs the merge base is more than a reformat.

    The swap-radius rule gates real backend SWAPS, not mechanical reformats. A
    repo-wide ``ruff format`` + safe ``--fix`` (a one-time lint baseline)
    rewrites files across every ring at once -- import removals and line
    rejoining included -- which would otherwise read as a false swap-radius
    violation the moment any unrelated ``services/*.py`` also changed.

    Git glue around :func:`_reformatted_matches`. Conservative fallbacks (keep the
    gate firing -- never silently drop a possible real swap): if git can't show
    either version, treat the change as substantive.
    """
    merge_base = _git("merge-base", "HEAD", default_branch)
    if not merge_base:
        return True
    old = _git("show", f"{merge_base}:{path}")
    new_path = _REPO_ROOT / path
    if old is None or not new_path.exists():
        return True
    return not _reformatted_matches(old, new_path.read_text())


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
            p for p in changed if p.startswith("services/") and _is_source_file(p)
        ]
        adapter_changes = [
            p
            for p in changed
            if p.startswith("agent_ui_adapter/")
            and _is_source_file(p)
            and _has_substantive_change(default_branch, p)
        ]

        # Mirror the same format-only filter on the service side, so a repo-wide
        # reformat that only touched whitespace doesn't trip the gate at all.
        service_changes = [
            p for p in service_changes if _has_substantive_change(default_branch, p)
        ]

        if not service_changes:
            pytest.skip("no substantive services/*.py source changes in this range")

        assert not adapter_changes, (
            "M-Phase2 swap-radius violation: backend service swap must not "
            "touch the adapter ring.\n"
            f"  Service changes: {service_changes}\n"
            f"  Adapter changes: {adapter_changes}\n"
            "If this is intentional (not a backend swap), this test can be "
            "skipped with -k 'not swap_radius'."
        )


class TestReformattedMatchesDiscriminator:
    """Direct unit tests for the format-only discriminator (review #3).

    ``_reformatted_matches`` decides whether the swap-radius gate fires. Without
    these, a refactor could silently invert it and the gate would stop firing on
    real swaps (the G8 risk, applied to this gate's own logic). Skipped when no
    ruff is available OR the repo root is not writable (the discriminator cannot
    host its config-resolving tempfile; the gate falls back to treating every
    change as substantive, which is the conservative-fire direction)."""

    _OLD_BADLY_FORMATTED = (
        "import os\n"
        "import sys\n"
        "\n\n"
        "def f(x):\n"
        "    y =  x+1\n"  # extra space + no spaces around +: ruff format fixes
        "    return y\n"
    )

    def _skip_if_cannot_run(self) -> None:
        ruff = _ruff_bin()
        if ruff is None:
            pytest.skip("no ruff available to run the discriminator")
        if not _repo_root_writable():
            pytest.skip(
                "repo root not writable, cannot host the discriminator tempfile"
            )

    def test_pure_reformat_is_format_only(self) -> None:
        """OLD reformatted by ruff == NEW (the reformatted text) ⇒ format-only."""
        self._skip_if_cannot_run()
        # Produce the canonical reformat of OLD by running ruff on it once.
        new_text = _canonical_reformat(self._OLD_BADLY_FORMATTED)
        # OLD differs from NEW only by formatting/safe-fixes ⇒ matches ⇒ True.
        assert _reformatted_matches(self._OLD_BADLY_FORMATTED, new_text) is True

    def test_unused_import_removal_is_format_only(self) -> None:
        """Removing an unused import is a safe ``--fix``, so it's NOT a swap.

        This is the case ``git diff -w`` gets wrong (it's a non-whitespace token
        change) — the ruff-equivalence discriminator must classify it format-only."""
        self._skip_if_cannot_run()
        old = "import os\nimport sys\n\n\ndef f():\n    return sys.argv\n"
        # NEW = same, but the unused `import os` removed (what ruff --fix F401 does).
        new = _canonical_reformat(old)
        assert "import os" not in new  # sanity: ruff did remove it
        assert _reformatted_matches(old, new) is True

    def test_semantic_edit_is_substantive(self) -> None:
        """A real logic change (new appended statement) is NOT format-only."""
        self._skip_if_cannot_run()
        old = "def f(x):\n    return x + 1\n"
        new = "def f(x):\n    return x + 2\n"  # changed the constant: a real swap
        assert _reformatted_matches(old, new) is False


def _canonical_reformat(text: str) -> str:
    """Run the same ruff (format + plain --fix) the discriminator uses, returning
    the reformatted text. Test helper so the 'NEW' side of a format-only pair is
    exactly what the discriminator would produce.

    Skips the calling test when _REPO_ROOT is not writable (some hardened CI
    runners mount the checkout read-only); the discriminator's production path
    returns False in that case, so the gate stays conservative-fire and these
    unit tests simply can't exercise the equivalence here."""
    import tempfile

    ruff = _ruff_bin()
    assert ruff is not None  # guarded by skip in callers
    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, dir=_REPO_ROOT
        ) as fh:
            fh.write(text)
            tmp = Path(fh.name)
    except OSError as exc:
        pytest.skip(f"repo root not writable, cannot run ruff discriminator: {exc}")
    try:
        subprocess.run(
            [ruff, "format", "-q", str(tmp)],
            capture_output=True,
            cwd=_REPO_ROOT,
            timeout=30,
        )
        subprocess.run(
            [ruff, "check", "-q", "--fix", str(tmp)],
            capture_output=True,
            cwd=_REPO_ROOT,
            timeout=30,
        )
        return tmp.read_text()
    finally:
        tmp.unlink(missing_ok=True)
