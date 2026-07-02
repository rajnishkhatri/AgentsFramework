"""L1 contract tests for the SessionStart AGENTS.md re-inject hook.

Failure-paths-first: the hook's HOOK-3 fail-safe (malformed stdin → silent
exit 0, no output) is asserted FIRST via subprocess, because a SessionStart
hook that crashes or emits garbage after every compaction would poison each
freshly-compacted context. Next comes the ``source == "compact"`` gate (the
whole reason this lives on SessionStart rather than the context-injecting-
incapable PostCompact event), then the pure subtree-detection and
payload-budget functions — tested in isolation, no git, no live anything.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_HOOK = _AGENT_ROOT / "scripts" / "hooks" / "sessionstart_reinject.py"


def _load():
    spec = importlib.util.spec_from_file_location("sessionstart_reinject", _HOOK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- HOOK-3 fail-safe first -------------------------------------------------


def test_malformed_stdin_is_silent_noop() -> None:
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="not json {",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_empty_stdin_does_not_crash() -> None:
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    # Empty payload is treated as valid-but-empty (no "compact" source) → the
    # gate makes it a silent no-op. Any output must still be parseable JSON.
    if proc.stdout.strip():
        json.loads(proc.stdout)


# --- source == "compact" gate ------------------------------------------------


def test_non_compact_source_is_silent_noop() -> None:
    """A fresh startup/resume/clear must NOT re-inject — only compaction drops
    the lazily-loaded nested guides. Asserted via subprocess so the real git
    detection runs and we still get no output for a non-compact source."""
    for source in ("startup", "resume", "clear"):
        proc = subprocess.run(
            [sys.executable, str(_HOOK)],
            input=json.dumps({"source": source}),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, source
        assert proc.stdout.strip() == "", source


def test_compact_source_emits_sessionstart_context_when_changes_exist() -> None:
    """With source=="compact" and repo edits present (this working tree always
    has changes during a session), the hook emits a well-formed SessionStart
    additionalContext payload — the delivery contract PostCompact could not."""
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({"source": "compact"}),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    # In a clean tree there may be nothing to inject (valid silence). When it
    # DOES speak, the shape must be the SessionStart contract — never the
    # schema-rejected PostCompact one.
    if proc.stdout.strip():
        out = json.loads(proc.stdout)
        assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "additionalContext" in out["hookSpecificOutput"]


# --- pure subtree detection ---------------------------------------------------


def test_active_agents_files_maps_paths_to_nested_guides() -> None:
    mod = _load()
    agents_dirs = ["trust", "services", "components", "scripts/hooks"]
    changed = [
        "trust/models.py",
        "trust/crypto.py",
        "services/governance/eval_graduation.py",
    ]
    assert mod.active_agents_files(changed, agents_dirs) == [
        "services/AGENTS.md",
        "trust/AGENTS.md",
    ]


def test_active_agents_files_deepest_dir_wins() -> None:
    mod = _load()
    # scripts/hooks has its own guide; a file under it must map there, not
    # to any shallower ancestor.
    agents_dirs = ["scripts/hooks"]
    changed = ["scripts/hooks/sessionstart_reinject.py"]
    assert mod.active_agents_files(changed, agents_dirs) == ["scripts/hooks/AGENTS.md"]


def test_active_agents_files_no_match_is_empty() -> None:
    mod = _load()
    # docs/ has no nested AGENTS.md → nothing to re-inject (the root guide is
    # auto-reloaded by the harness after compaction; we never duplicate it).
    assert mod.active_agents_files(["docs/adr/log.md"], ["trust"]) == []
    assert mod.active_agents_files([], ["trust"]) == []


# --- bounded payload ----------------------------------------------------------


def test_build_context_within_budget_includes_content() -> None:
    mod = _load()
    contents = {"trust/AGENTS.md": "TRUST RULES"}
    ctx = mod.build_context(["trust/AGENTS.md"], contents.get, budget=10_000)
    assert "TRUST RULES" in ctx
    assert "trust/AGENTS.md" in ctx


def test_build_context_over_budget_falls_back_to_path_list() -> None:
    mod = _load()
    big = "x" * 50_000
    contents = {"trust/AGENTS.md": big, "services/AGENTS.md": big}
    ctx = mod.build_context(
        ["trust/AGENTS.md", "services/AGENTS.md"], contents.get, budget=1_000
    )
    assert len(ctx) <= 2_000  # bounded: never dumps the oversized bodies
    assert "trust/AGENTS.md" in ctx and "services/AGENTS.md" in ctx


# --- output shape ---------------------------------------------------------------


def test_render_output_shape() -> None:
    mod = _load()
    out = mod.render_output("some context")
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert out["hookSpecificOutput"]["additionalContext"] == "some context"
