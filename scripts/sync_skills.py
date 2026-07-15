#!/usr/bin/env python3
"""Sync canonical ``docs/skills/`` bundles to the per-agent discovery mirrors.

Canonical home: ``docs/skills/<name>/`` (OKF bundle — linted, PR-reviewed).
Each supported coding agent is an **adapter** in the ``ADAPTERS`` registry: it
declares its discovery path and a projection from a canonical skill dir to the
files it wants written there. Adding a new agent is one registry entry — no
change to the sync/check core (ADR-0032).

Adapters today:
  * ``ClaudeAdapter`` → ``.claude/skills/`` (Claude Code) — identity byte-copy.
  * ``CursorAdapter`` → ``.cursor/skills/`` (Cursor) — identity byte-copy.
  * ``CopilotAdapter`` → ``.github/`` — thin ``*.instructions.md`` pointers
    (never a prose copy); see ``_copilot_project``.

Rules:
  * Identity adapters copy **verbatim** (byte-identical) — mirrors are read by
    the model, which resolves repo paths from prose; markdown-relative links are
    not localized per mirror.
  * Evidence and packaging are not mirrored: ``*-workspace/`` dirs, ``evals/``
    dirs, ``*.skill`` archives, ``__pycache__``.
  * Inside a *managed* skill dir (one that exists in canonical) the mirror is
    made exact: missing files are written, stale files are deleted. Mirror-only
    skill dirs (e.g. ``.cursor/skills/deploy-gcp`` — TODO: adopt into
    ``docs/skills/``) are left untouched.

Usage:
    python scripts/sync_skills.py            # write all adapter projections
    python scripts/sync_skills.py --check    # no writes; exit 1 + report on drift

``tests/architecture/test_skills_mirror_parity.py`` runs the ``--check`` core,
so CI fails on drift and there is exactly one definition of "in sync".
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "docs" / "skills"

_EXCLUDED_DIR_NAMES = {"evals", "__pycache__"}
_EXCLUDED_FILE_NAMES = {".DS_Store"}
_EXCLUDED_FILE_SUFFIXES = (".skill", ".pyc")

# Only these skills project to the Copilot adapter today: the portable SDD set.
# The rest stay Claude/Cursor-only until adopted (kept explicit, not silent).
_COPILOT_SKILLS = (
    "sdd-lifecycle",
    "sdd-brainstorm",
    "sdd-spec",
    "sdd-replan",
    "sdd-implement",
    "sdd-converge",
)


def _excluded_dir(name: str) -> bool:
    return (
        name in _EXCLUDED_DIR_NAMES
        or name.endswith("-workspace")
        or name.startswith(".")
    )


def _excluded_file(name: str) -> bool:
    return name in _EXCLUDED_FILE_NAMES or name.endswith(_EXCLUDED_FILE_SUFFIXES)


def _display_path(path: Path) -> str:
    """Repo-relative posix path for logging, or the absolute path if the target
    lives outside the repo root (an adapter is not required to — e.g. a test
    fixture pointing at a tmp dir). Keeps prod output identical while staying
    robust for any registry entry."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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


def _identity_project(name: str, source_dir: Path) -> dict[str, bytes]:
    """Byte-identical projection: the mirror IS the canonical skill dir."""
    return skill_files(source_dir)


def _copilot_project(name: str, source_dir: Path) -> dict[str, bytes]:
    """Thin ``*.instructions.md`` pointer — never a prose copy (ADR-0032).

    Only the portable SDD skills project to Copilot. Each becomes a
    ``sdd-<name>.instructions.md`` file with ``applyTo`` frontmatter and a single
    one-line pointer back to the canonical ``docs/skills/<name>/SKILL.md`` — the
    reading agent resolves the full skill there, exactly as the ``.cursor/rules``
    pointers do. Emits nothing for non-Copilot skills.
    """
    if name not in _COPILOT_SKILLS:
        return {}
    pointer = (
        f"---\n"
        f'applyTo: "**"\n'
        f"---\n\n"
        f"See `docs/skills/{name}/SKILL.md` for the {name} skill.\n"
    )
    return {f"instructions/{name}.instructions.md": pointer.encode()}


def _copilot_repo_wide() -> tuple[str, bytes]:
    """The repo-wide ``.github/copilot-instructions.md`` pointer (one file)."""
    lines = [
        "# Copilot instructions",
        "",
        "This repository ships portable spec-driven-development (SDD) skills.",
        "Path-specific SDD guidance lives in `.github/instructions/`; each file "
        "points at the canonical skill under `docs/skills/`.",
        "",
    ]
    return "copilot-instructions.md", ("\n".join(lines)).encode()


class Adapter(NamedTuple):
    """One coding agent's discovery projection.

    ``base_dir`` is the agent's discovery root; ``project`` maps a canonical
    skill dir to the files this agent wants written under ``base_dir/<subdir>``.
    ``per_skill_subdir`` places identity mirrors under ``base_dir/<name>/`` (the
    ``.claude``/``.cursor`` layout); Copilot writes flat under ``base_dir``.

    A ``NamedTuple`` (not a dataclass) so the module loads under
    ``importlib.util.exec_module`` without being registered in ``sys.modules``
    — the pattern ``test_skills_mirror_parity.py`` uses.
    """

    name: str
    base_dir: Path
    project: Callable[[str, Path], dict[str, bytes]]
    per_skill_subdir: bool
    repo_wide: Callable[[], tuple[str, bytes]] | None = None

    def expected_files(self, source: Path = SOURCE) -> dict[str, bytes]:
        """All files this adapter should own: base_dir-relative posix path → bytes."""
        out: dict[str, bytes] = {}
        for skill in skill_names(source):
            projected = self.project(skill, source / skill)
            for rel, body in projected.items():
                prefix = f"{skill}/" if self.per_skill_subdir else ""
                out[f"{prefix}{rel}"] = body
        if self.repo_wide is not None:
            rel, body = self.repo_wide()
            out[rel] = body
        return out


# The registry. Adding a coding agent is ONE entry here (ADR-0032).
ADAPTERS: tuple[Adapter, ...] = (
    Adapter("claude", REPO_ROOT / ".claude" / "skills", _identity_project, True),
    Adapter("cursor", REPO_ROOT / ".cursor" / "skills", _identity_project, True),
    Adapter(
        "copilot",
        REPO_ROOT / ".github",
        _copilot_project,
        False,
        repo_wide=_copilot_repo_wide,
    ),
)


def _actual_files(adapter: Adapter) -> dict[str, bytes]:
    """Files currently present under an adapter's managed paths.

    Only paths the adapter *could* own are scanned, so unrelated files under a
    shared base dir (e.g. ``.github/workflows/``) are never flagged as stale.
    """
    expected = adapter.expected_files()
    owned_prefixes = {rel.split("/", 1)[0] for rel in expected}
    actual: dict[str, bytes] = {}
    for rel in expected:
        path = adapter.base_dir / rel
        if path.is_file():
            actual[rel] = path.read_bytes()
    # Detect stale files only within per-skill subdirs the adapter manages
    # (identity mirrors delete removed files); flat adapters own exact paths only.
    if adapter.per_skill_subdir:
        for top in owned_prefixes:
            skill_dir = adapter.base_dir / top
            if not skill_dir.is_dir():
                continue
            for path in sorted(skill_dir.rglob("*")):
                if not path.is_file() or _excluded_file(path.name):
                    continue
                rel = path.relative_to(adapter.base_dir).as_posix()
                if any(
                    _excluded_dir(p) for p in path.relative_to(skill_dir).parts[:-1]
                ):
                    continue
                actual.setdefault(rel, path.read_bytes())
    return actual


def check(source: Path = SOURCE) -> list[str]:
    """Drift report — empty means every adapter projection is up to date."""
    problems: list[str] = []
    for adapter in ADAPTERS:
        expected = adapter.expected_files(source)
        actual = _actual_files(adapter)
        for rel in sorted(set(expected) - set(actual)):
            problems.append(f"{adapter.name}:{rel}: missing (run `make skills-sync`)")
        for rel in sorted(set(actual) - set(expected)):
            problems.append(f"{adapter.name}:{rel}: stale (not in canonical)")
        for rel in sorted(set(expected) & set(actual)):
            if expected[rel] != actual[rel]:
                problems.append(f"{adapter.name}:{rel}: differs from canonical")
    return problems


def sync(source: Path = SOURCE) -> list[str]:
    """Make every adapter projection exact. Returns actions."""
    actions: list[str] = []
    for adapter in ADAPTERS:
        expected = adapter.expected_files(source)
        actual = _actual_files(adapter)
        for rel, body in expected.items():
            if actual.get(rel) == body:
                continue
            dest = adapter.base_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            actions.append(f"wrote {_display_path(dest)}")
        for rel in set(actual) - set(expected):
            dest = adapter.base_dir / rel
            dest.unlink()
            actions.append(f"removed {_display_path(dest)}")
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
