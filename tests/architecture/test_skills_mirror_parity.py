"""Skills-mirror parity gate.

Canonical skills live in ``docs/skills/`` (OKF bundle). Auto-trigger requires
copies in the discovery paths ``.claude/skills/`` + ``.cursor/skills/`` — those
mirrors are a *mechanical projection*, synced by ``scripts/sync_skills.py``
(``make skills-sync``). This test runs the script's own ``--check`` core so CI
fails on any drift and there is exactly one definition of "in sync".

Mirror-only dirs are NOT flagged: ``.cursor/skills/deploy-gcp`` predates the
sync convention and has no canonical bundle yet (TODO: adopt it into
``docs/skills/`` and let the sync manage it).
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


def test_every_canonical_skill_is_mirrored_byte_identical() -> None:
    mod = _load()
    problems = mod.check()
    assert problems == [], (
        "skills mirrors drifted from docs/skills/ — run `make skills-sync` "
        "and stage the result:\n" + "\n".join(problems)
    )


def test_sdd_skills_present_in_canonical_bundle() -> None:
    """The SDD lifecycle family must exist as canonical bundles (Part B)."""
    mod = _load()
    names = set(mod.skill_names())
    expected = {
        "sdd-lifecycle",
        "sdd-brainstorm",
        "sdd-spec",
        "sdd-replan",
        "sdd-implement",
        "sdd-converge",
    }
    missing = sorted(expected - names)
    assert not missing, f"missing canonical sdd-* skill bundles: {missing}"
