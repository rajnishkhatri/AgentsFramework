#!/usr/bin/env python3
"""Emit portable ``.skill`` archives for the SDD lifecycle skills (ADR-0032).

A ``.skill`` archive is a zip whose top dir is ``<name>/`` — the format the
repo's existing tracked archives already use (``docs/skills/*.skill``). This
script makes the six SDD archives a *mechanical projection* of their source
dirs, the way ``sync_skills.py`` does for the discovery mirrors, so they can't
silently drift from the skills they package.

Each SDD archive is self-contained for drop-in into a foreign workspace: it
carries the portable ``SKILL.md`` plus the workspace-binding contract
(``binding.template.toml`` to fill, ``binding.schema.md`` reference, and
``FIRST_RUN.md`` describing the inspect→propose→confirm→persist auto-adapt).

It also emits ONE all-in-one export bundle, ``docs/skills/sdd-skills-bundle.zip``
— every SDD skill + the shared workspace-binding contract + an ``INSTALL.md``
how-to under a single ``sdd-skills-bundle/`` top dir, so a user has one file to
drop into any workspace and any coding agent. The bundle is a **build-on-demand
artifact** — ``.gitignore``-d, not tracked — so ``check`` treats its absence as
fine and only flags a *present* copy that has drifted from source.

Determinism: members are written in sorted order with a fixed timestamp, so the
bytes are reproducible across machines and ``--check`` is stable.

Usage:
    python scripts/pack_skills.py            # write sdd-*.skill + the bundle
    python scripts/pack_skills.py --check    # no writes; exit 1 on drift

``tests/architecture/test_skills_pack.py`` runs the ``--check`` core.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "docs" / "skills"
_SDD_BUNDLE = SOURCE / "_sdd"

# The six portable SDD skills that get packaged. Explicit (not a glob) so a new
# unrelated skill dir is never auto-shipped.
SDD_SKILLS = (
    "sdd-lifecycle",
    "sdd-brainstorm",
    "sdd-spec",
    "sdd-replan",
    "sdd-implement",
    "sdd-converge",
)

# The binding-contract files bundled into every SDD archive (FR-17). The
# template is what a consumer fills; the schema + FIRST_RUN explain how.
_BUNDLED_BINDING_FILES = (
    "binding.template.toml",
    "binding.schema.md",
    "FIRST_RUN.md",
)

# The single all-in-one export bundle: every SDD skill + the shared binding
# contract + an install guide, in one drop-into-any-workspace zip. Its top dir.
BUNDLE_NAME = "sdd-skills-bundle"
# The shared contract files placed at the bundle's top-level `_sdd/` (the master
# copy; each skill dir still carries its own for standalone use). INSTALL.md is
# the human how-to-install guide; the reference.toml is deliberately omitted — it
# holds THIS repo's own values and is not meaningful in a foreign workspace.
_BUNDLE_SHARED_FILES = (
    "INSTALL.md",
    "binding.schema.md",
    "binding.template.toml",
    "FIRST_RUN.md",
)

# Fixed member timestamp for reproducible archives (ZIP epoch is 1980).
_FIXED_MTIME = (1980, 1, 1, 0, 0, 0)


def archive_members(name: str) -> dict[str, bytes]:
    """The files an SDD ``.skill`` archive should contain: ``<name>/…`` → bytes.

    Raises ``FileNotFoundError`` if a required source file is missing — a
    packaging error should be loud, not a silently smaller archive.
    """
    skill_dir = SOURCE / name
    members: dict[str, bytes] = {}
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file() and not path.name.endswith((".pyc", ".skill")):
            rel = path.relative_to(skill_dir).as_posix()
            members[f"{name}/{rel}"] = path.read_bytes()
    for fname in _BUNDLED_BINDING_FILES:
        src = _SDD_BUNDLE / fname
        if not src.is_file():
            raise FileNotFoundError(f"binding file missing for archive: {src}")
        members[f"{name}/{fname}"] = src.read_bytes()
    return members


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    """Deterministic zip bytes: members in sorted order, fixed 1980 mtime, 0644.
    Shared by the per-skill archive and the all-in-one bundle so both reproduce
    byte-for-byte across machines and ``--check`` is stable for each."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname in sorted(members):
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_MTIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, members[arcname])
    return buf.getvalue()


def build_archive_bytes(name: str) -> bytes:
    """Deterministic zip bytes for one SDD skill archive."""
    return _zip_bytes(archive_members(name))


def bundle_members() -> dict[str, bytes]:
    """The files the all-in-one export bundle contains: ``sdd-skills-bundle/…``.

    Layout: the shared contract + install guide at the top level, then every
    skill dir (each still self-contained). This is a mechanical projection of the
    same sources the per-skill archives use — it can't silently drift from them.
    Raises ``FileNotFoundError`` if a shared source file is missing (a packaging
    error should be loud, not a silently smaller bundle).
    """
    members: dict[str, bytes] = {}
    for fname in _BUNDLE_SHARED_FILES:
        src = _SDD_BUNDLE / fname
        if not src.is_file():
            raise FileNotFoundError(f"bundle shared file missing: {src}")
        members[f"{BUNDLE_NAME}/_sdd/{fname}"] = src.read_bytes()
    for name in SDD_SKILLS:
        for rel, body in archive_members(name).items():
            # archive_members keys are already "<name>/…"; nest under the bundle.
            members[f"{BUNDLE_NAME}/{rel}"] = body
    return members


def build_bundle_bytes() -> bytes:
    """Deterministic zip bytes for the single all-in-one export bundle."""
    return _zip_bytes(bundle_members())


def _archive_path(name: str) -> Path:
    return SOURCE / f"{name}.skill"


def _bundle_path() -> Path:
    return SOURCE / f"{BUNDLE_NAME}.zip"


def _members_of(archive: Path) -> dict[str, bytes]:
    if not archive.is_file():
        return {}
    with zipfile.ZipFile(archive) as zf:
        return {n: zf.read(n) for n in sorted(zf.namelist())}


# Every emitted zip as (archive path, expected members, optional). One list drives
# both check() and pack(). `optional=True` marks a build-on-demand artifact that is
# NOT tracked in git (the all-in-one bundle): pack always (re)builds it, but check
# only compares it when it happens to be present — a fresh checkout without it is
# not "drift". The six per-skill `.skill` archives are tracked, so `optional=False`
# and a missing one IS drift.
def _targets() -> list[tuple[Path, dict[str, bytes], bool]]:
    targets: list[tuple[Path, dict[str, bytes], bool]] = [
        (_archive_path(name), archive_members(name), False) for name in SDD_SKILLS
    ]
    targets.append((_bundle_path(), bundle_members(), True))
    return targets


def check() -> list[str]:
    """Drift report — empty means every tracked archive matches its source.

    The build-on-demand bundle (``optional``) is untracked, so its absence is not
    drift; it is only compared when present (a stale checked-in copy would still
    be caught).
    """
    problems: list[str] = []
    for archive, expected, optional in _targets():
        label = archive.relative_to(REPO_ROOT).as_posix()
        if not archive.is_file():
            if not optional:
                problems.append(f"{label}: missing (run `make skills-pack`)")
            continue
        # Compare on member content, not raw bytes: a zip's stored order/metadata
        # can differ while contents match. The builders are deterministic, but
        # content comparison is the property that actually matters.
        actual = _members_of(archive)
        for rel in sorted(set(expected) - set(actual)):
            problems.append(f"{label}: missing member {rel}")
        for rel in sorted(set(actual) - set(expected)):
            problems.append(f"{label}: stale member {rel}")
        for rel in sorted(set(expected) & set(actual)):
            if expected[rel] != actual[rel]:
                problems.append(f"{label}: member {rel} differs from source")
    return problems


def pack() -> list[str]:
    """Write every SDD ``.skill`` archive + the bundle from source. Returns actions."""
    actions: list[str] = []
    for archive, expected, _optional in _targets():
        # Skip a rewrite when member content already matches (keeps the mtime
        # stable and `--check` honest even if raw bytes would differ).
        if archive.is_file() and _members_of(archive) == expected:
            continue
        archive.write_bytes(_zip_bytes(expected))
        actions.append(f"wrote {archive.relative_to(REPO_ROOT).as_posix()}")
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="report drift and exit 1; write nothing"
    )
    args = parser.parse_args(argv)
    if args.check:
        problems = check()
        for line in problems:
            print(line)
        if problems:
            print(f"{len(problems)} archive drift problem(s). Fix: make skills-pack")
            return 1
        print("skill archives in sync")
        return 0
    actions = pack()
    for line in actions:
        print(line)
    print(
        f"packed {len(SDD_SKILLS)} SDD skill archive(s) + 1 all-in-one bundle "
        f"({BUNDLE_NAME}.zip)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
