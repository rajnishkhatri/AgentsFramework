#!/usr/bin/env python3
"""Sync canonical ``docs/skills/`` bundles to the skill-discovery mirrors.

Canonical home: ``docs/skills/<name>/`` (OKF bundle — linted, PR-reviewed).
Mirrors: ``.claude/skills/`` (Claude Code project skills) and
``.cursor/skills/`` (Cursor). Auto-trigger requires the skills to live in a
discovery path, so the mirrors are load-bearing — this script makes them a
mechanical projection instead of a by-hand convention (which had already
drifted; see docs/adr/decisions.md 2026-07-02).

Rules:
  * Copy is **verbatim** (byte-identical) — mirrors are read by the model,
    which resolves repo paths from prose; markdown-relative links are not
    localized per mirror.
  * Evidence and packaging are not mirrored: ``*-workspace/`` dirs, ``evals/``
    dirs, ``*.skill`` archives, ``__pycache__``.
  * Inside a *managed* skill dir (one that exists in canonical) the mirror is
    made exact: missing files are written, stale files are deleted. Mirror-only
    skill dirs (e.g. ``.cursor/skills/deploy-gcp`` — TODO: adopt into
    ``docs/skills/``) are left untouched.

Usage:
    python scripts/sync_skills.py            # write mirrors
    python scripts/sync_skills.py --check    # no writes; exit 1 + report on drift

``tests/architecture/test_skills_mirror_parity.py`` runs the ``--check`` core,
so CI fails on drift and there is exactly one definition of "in sync".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "docs" / "skills"
TARGETS = (REPO_ROOT / ".claude" / "skills", REPO_ROOT / ".cursor" / "skills")

_EXCLUDED_DIR_NAMES = {"evals", "__pycache__"}
_EXCLUDED_FILE_NAMES = {".DS_Store"}
_EXCLUDED_FILE_SUFFIXES = (".skill", ".pyc")


def _excluded_dir(name: str) -> bool:
    return (
        name in _EXCLUDED_DIR_NAMES
        or name.endswith("-workspace")
        or name.startswith(".")
    )


def _excluded_file(name: str) -> bool:
    return name in _EXCLUDED_FILE_NAMES or name.endswith(_EXCLUDED_FILE_SUFFIXES)


def skill_names(source: Path = SOURCE) -> list[str]:
    """Canonical skill-bundle dir names (each must hold a SKILL.md)."""
    if not source.is_dir():
        return []
    return sorted(
        child.name
        for child in source.iterdir()
        if child.is_dir()
        and not _excluded_dir(child.name)
        and (child / "SKILL.md").is_file()
    )


def skill_files(skill_dir: Path) -> dict[str, bytes]:
    """Mirror-worthy files of one skill dir: relative posix path → bytes."""
    files: dict[str, bytes] = {}
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir)
        if any(_excluded_dir(part) for part in rel.parts[:-1]) or _excluded_file(
            rel.name
        ):
            continue
        files[rel.as_posix()] = path.read_bytes()
    return files


def check(source: Path = SOURCE, targets: tuple[Path, ...] = TARGETS) -> list[str]:
    """Drift report — empty means every mirror matches canonical byte-for-byte."""
    problems: list[str] = []
    for name in skill_names(source):
        expected = skill_files(source / name)
        for target in targets:
            mirror = target / name
            label = mirror.relative_to(REPO_ROOT).as_posix()
            if not mirror.is_dir():
                problems.append(f"{label}: missing (run `make skills-sync`)")
                continue
            actual = skill_files(mirror)
            for rel in sorted(set(expected) - set(actual)):
                problems.append(f"{label}/{rel}: missing")
            for rel in sorted(set(actual) - set(expected)):
                problems.append(f"{label}/{rel}: stale (not in canonical)")
            for rel in sorted(set(expected) & set(actual)):
                if expected[rel] != actual[rel]:
                    problems.append(
                        f"{label}/{rel}: differs from docs/skills/{name}/{rel}"
                    )
    return problems


def sync(source: Path = SOURCE, targets: tuple[Path, ...] = TARGETS) -> list[str]:
    """Make every mirror an exact projection of canonical. Returns actions."""
    actions: list[str] = []
    for name in skill_names(source):
        expected = skill_files(source / name)
        for target in targets:
            mirror = target / name
            actual = skill_files(mirror) if mirror.is_dir() else {}
            for rel, body in expected.items():
                if actual.get(rel) == body:
                    continue
                dest = mirror / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(body)
                actions.append(f"wrote {dest.relative_to(REPO_ROOT).as_posix()}")
            for rel in set(actual) - set(expected):
                (mirror / rel).unlink()
                actions.append(
                    f"removed {(mirror / rel).relative_to(REPO_ROOT).as_posix()}"
                )
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
            print(f"{len(problems)} mirror drift problem(s). Fix: make skills-sync")
            return 1
        print("skills mirrors in sync")
        return 0
    for line in sync():
        print(line)
    print("skills mirrors synced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
