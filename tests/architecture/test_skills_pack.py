"""SDD ``.skill`` archive emitter gate (spec FR-16/FR-18/FR-19).

``scripts/pack_skills.py`` projects each portable SDD skill dir into a
``docs/skills/<name>.skill`` zip that carries the skill plus the workspace-binding
contract, so a foreign workspace can drop it in. Guards:

  * FR-19 — exactly the six SDD archives are emitted.
  * FR-16/FR-17 — each archive has the ``<name>/`` top dir, its ``SKILL.md``, and
    the bundled binding files (template + schema + FIRST_RUN).
  * FR-18 — ``--check`` detects drift between an archive and its source.

Loaded via ``importlib`` (import-safe under ``exec_module``).
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_PACK = _AGENT_ROOT / "scripts" / "pack_skills.py"
_SKILLS = _AGENT_ROOT / "docs" / "skills"

_SDD_SKILLS = (
    "sdd-lifecycle",
    "sdd-brainstorm",
    "sdd-spec",
    "sdd-replan",
    "sdd-implement",
    "sdd-converge",
)
_BUNDLED = ("binding.template.toml", "binding.schema.md", "FIRST_RUN.md")


def _load():
    spec = importlib.util.spec_from_file_location("pack_skills", _PACK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emits_six_sdd_archives() -> None:
    """FR-19: exactly the six SDD archives exist on disk after packing."""
    mod = _load()
    assert set(mod.SDD_SKILLS) == set(_SDD_SKILLS), mod.SDD_SKILLS
    missing = [n for n in _SDD_SKILLS if not (_SKILLS / f"{n}.skill").is_file()]
    assert not missing, (
        f"SDD .skill archives not emitted (run `make skills-pack`): {missing}"
    )


def test_archive_layout_and_binding_bundle() -> None:
    """FR-16/FR-17: <name>/ top dir + SKILL.md + bundled binding files."""
    for name in _SDD_SKILLS:
        archive = _SKILLS / f"{name}.skill"
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
        assert f"{name}/SKILL.md" in names, f"{archive.name} missing {name}/SKILL.md"
        for fname in _BUNDLED:
            assert f"{name}/{fname}" in names, f"{archive.name} missing {name}/{fname}"
        assert all(n.startswith(f"{name}/") for n in names), (
            f"{archive.name} has members outside the {name}/ top dir: "
            f"{sorted(n for n in names if not n.startswith(f'{name}/'))}"
        )


def test_pack_check_detects_drift(tmp_path) -> None:
    """FR-18: check() reports drift when an archive no longer matches its source."""
    mod = _load()
    # With committed archives in sync, check() is clean.
    assert mod.check() == [], mod.check()
    # Corrupt one archive in place, confirm check() flags it, then restore.
    target = _SKILLS / "sdd-lifecycle.skill"
    original = target.read_bytes()
    backup = tmp_path / "backup.skill"
    backup.write_bytes(original)
    try:
        with zipfile.ZipFile(target, "a") as zf:
            zf.writestr("sdd-lifecycle/INTRUDER.md", b"drift")
        problems = mod.check()
        assert any("sdd-lifecycle.skill" in p for p in problems), (
            f"check() did not detect the injected drift: {problems}"
        )
    finally:
        target.write_bytes(backup.read_bytes())
    assert mod.check() == [], "restore failed — archive left drifted"


def test_bundle_is_complete() -> None:
    """The all-in-one bundle holds the shared contract + every skill, self-contained.

    The bundle is a build-on-demand artifact (NOT tracked in git), so this asserts
    on what the emitter *produces* from source, not on a committed file — it holds
    whether or not `make skills-pack` has been run in this checkout.
    """
    mod = _load()
    names = set(mod.bundle_members())
    top = mod.BUNDLE_NAME
    # Shared contract + install guide at the top-level _sdd/.
    for fname in (
        "INSTALL.md",
        "binding.schema.md",
        "binding.template.toml",
        "FIRST_RUN.md",
    ):
        assert f"{top}/_sdd/{fname}" in names, f"bundle missing {top}/_sdd/{fname}"
    # Every skill present and self-contained (its own SKILL.md + binding files).
    for name in _SDD_SKILLS:
        assert f"{top}/{name}/SKILL.md" in names, (
            f"bundle missing {top}/{name}/SKILL.md"
        )
        for fname in _BUNDLED:
            assert f"{top}/{name}/{fname}" in names, (
                f"bundle missing {top}/{name}/{fname}"
            )
    # Nothing escapes the single bundle top dir.
    assert all(n.startswith(f"{top}/") for n in names), (
        f"bundle has members outside {top}/: "
        f"{sorted(n for n in names if not n.startswith(f'{top}/'))}"
    )
    # The reference binding (this-repo values) must NOT ship — it is meaningless
    # in a foreign workspace and would mislead a consumer.
    assert not any("binding.reference.toml" in n for n in names), (
        "bundle must not ship binding.reference.toml (this-repo-only values)"
    )


def test_bundle_check_detects_drift_when_present() -> None:
    """FR-18 (bundle): a *present* bundle that no longer matches source is drift.

    The bundle is untracked/build-on-demand, so its absence is NOT drift — that
    is asserted in test_bundle_absence_is_not_drift. When it IS present, check()
    must still catch a stale copy. We build it, corrupt it, verify, restore.
    """
    mod = _load()
    target = _SKILLS / f"{mod.BUNDLE_NAME}.zip"
    was_present = target.is_file()
    backup = target.read_bytes() if was_present else None
    try:
        target.write_bytes(mod.build_bundle_bytes())  # ensure an in-sync bundle
        assert mod.check() == [], mod.check()
        with zipfile.ZipFile(target, "a") as zf:
            zf.writestr(f"{mod.BUNDLE_NAME}/INTRUDER.md", b"drift")
        problems = mod.check()
        assert any(f"{mod.BUNDLE_NAME}.zip" in p for p in problems), (
            f"check() did not detect injected bundle drift: {problems}"
        )
    finally:
        if backup is not None:
            target.write_bytes(backup)
        elif target.is_file():
            target.unlink()  # leave the tree as we found it (untracked artifact)


def test_bundle_absence_is_not_drift() -> None:
    """The untracked bundle being absent is NOT flagged by check() (build-on-demand)."""
    mod = _load()
    target = _SKILLS / f"{mod.BUNDLE_NAME}.zip"
    saved = target.read_bytes() if target.is_file() else None
    try:
        if target.is_file():
            target.unlink()
        problems = mod.check()
        assert not any(f"{mod.BUNDLE_NAME}.zip" in p for p in problems), (
            f"absent build-on-demand bundle wrongly reported as drift: {problems}"
        )
    finally:
        if saved is not None:
            target.write_bytes(saved)
