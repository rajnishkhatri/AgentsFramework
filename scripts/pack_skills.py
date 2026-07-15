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

Determinism: members are written in sorted order with a fixed timestamp, so the
bytes are reproducible across machines and ``--check`` is stable.

Usage:
    python scripts/pack_skills.py            # write docs/skills/sdd-*.skill
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


def build_archive_bytes(name: str) -> bytes:
    """Deterministic zip bytes for one SDD skill archive."""
    members = archive_members(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname in sorted(members):
            info = zipfile.ZipInfo(arcname, date_time=_FIXED_MTIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, members[arcname])
    return buf.getvalue()


def _archive_path(name: str) -> Path:
    return SOURCE / f"{name}.skill"


def _members_of(archive: Path) -> dict[str, bytes]:
    if not archive.is_file():
        return {}
    with zipfile.ZipFile(archive) as zf:
        return {n: zf.read(n) for n in sorted(zf.namelist())}


def check() -> list[str]:
    """Drift report — empty means every SDD archive matches its source dir."""
    problems: list[str] = []
    for name in SDD_SKILLS:
        archive = _archive_path(name)
        label = archive.relative_to(REPO_ROOT).as_posix()
        if not archive.is_file():
            problems.append(f"{label}: missing (run `make skills-pack`)")
            continue
        # Compare on member content, not raw bytes: a zip's stored order/metadata
        # can differ while contents match. build_archive_bytes is deterministic,
        # but content comparison is the property that actually matters.
        expected = archive_members(name)
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
    """Write every SDD ``.skill`` archive from its source. Returns actions."""
    actions: list[str] = []
    for name in SDD_SKILLS:
        archive = _archive_path(name)
        new_bytes = build_archive_bytes(name)
        # Skip a rewrite when member content already matches (keeps the mtime
        # stable and `--check` honest even if raw bytes would differ).
        if archive.is_file() and _members_of(archive) == archive_members(name):
            continue
        archive.write_bytes(new_bytes)
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
    print(f"packed {len(SDD_SKILLS)} SDD skill archive(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
