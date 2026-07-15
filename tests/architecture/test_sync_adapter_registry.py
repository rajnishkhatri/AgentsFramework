"""Adapter-registry gate for scripts/sync_skills.py (spec FR-11/FR-12).

The sync layer projects canonical ``docs/skills/`` bundles to each coding
agent's discovery path via an ``ADAPTERS`` registry (ADR-0032). Two properties
this gate locks in:

  * FR-11 — adding a coding agent is ONE registry entry: a fresh adapter is
    picked up by ``check``/``sync`` with no change to the core loop.
  * FR-12 — ``check`` reports drift per-adapter (not just the original two
    fixed mirror paths).

Loaded via ``importlib`` the same way ``test_skills_mirror_parity.py`` does, so
the module must stay import-safe under ``exec_module`` (hence ``Adapter`` is a
``NamedTuple``, not a dataclass).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_SYNC = _AGENT_ROOT / "scripts" / "sync_skills.py"


def _load():
    spec = importlib.util.spec_from_file_location("sync_skills", _SYNC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_registry_has_the_three_agents() -> None:
    mod = _load()
    names = [a.name for a in mod.ADAPTERS]
    assert names == ["claude", "cursor", "copilot"], names


def test_check_iterates_every_registered_adapter(monkeypatch, tmp_path) -> None:
    """FR-12: a new adapter's drift is reported — check() is not hard-wired to two."""
    mod = _load()
    # A fresh adapter pointing at an empty temp dir MUST surface as drift
    # (its expected files are missing), proving check() covers the whole registry.
    fresh = mod.Adapter(
        name="fixture",
        base_dir=tmp_path / "fixture-agent",
        project=mod._identity_project,
        per_skill_subdir=True,
    )
    monkeypatch.setattr(mod, "ADAPTERS", (*mod.ADAPTERS, fresh))
    problems = mod.check()
    assert any(p.startswith("fixture:") for p in problems), (
        "check() did not report the fresh adapter's drift — registry not iterated:\n"
        + "\n".join(problems)
    )


def test_new_adapter_is_one_entry(monkeypatch, tmp_path) -> None:
    """FR-11: sync() picks up a new adapter with no core-logic change, then it's clean."""
    mod = _load()
    fresh = mod.Adapter(
        name="fixture",
        base_dir=tmp_path / "fixture-agent",
        project=mod._identity_project,
        per_skill_subdir=True,
    )
    monkeypatch.setattr(mod, "ADAPTERS", (*mod.ADAPTERS, fresh))
    actions = mod.sync()
    assert any("fixture-agent" in a for a in actions), (
        "sync() wrote nothing for the fresh adapter — it was not picked up"
    )
    # After sync the fixture adapter must be drift-free (round-trips through check).
    remaining = [p for p in mod.check() if p.startswith("fixture:")]
    assert remaining == [], remaining


def test_the_real_registry_is_in_sync() -> None:
    """The committed projections (claude/cursor/copilot) have no drift."""
    mod = _load()
    problems = mod.check()
    assert problems == [], (
        "adapter projections drifted — run `make skills-sync`:\n" + "\n".join(problems)
    )
