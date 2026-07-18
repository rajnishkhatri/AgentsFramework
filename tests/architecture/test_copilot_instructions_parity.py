"""GitHub Copilot instructions parity gate (spec FR-13/FR-14/FR-15).

The Copilot adapter projects each portable SDD skill to a thin
``.github/instructions/sdd-<name>.instructions.md`` pointer — never a prose copy
(ADR-0032, mirroring the ``.cursor/rules/*.mdc`` pattern). Guards:

  * FR-13 — every pointer resolves to an existing ``docs/skills/<name>/SKILL.md``.
  * FR-14 — each file carries valid ``applyTo:`` glob frontmatter.
  * FR-15 — the body is a pointer only: frontmatter + a single ``see …`` line,
    no restated skill prose.

Verified Copilot format (GitHub docs, 2026): repo-wide
``.github/copilot-instructions.md``; path-specific
``.github/instructions/NAME.instructions.md`` with an ``applyTo`` frontmatter key.
"""

from __future__ import annotations

import re
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_INSTRUCTIONS = _AGENT_ROOT / ".github" / "instructions"
_REPO_WIDE = _AGENT_ROOT / ".github" / "copilot-instructions.md"
_SKILLS = _AGENT_ROOT / "docs" / "skills"

_SDD_SKILLS = (
    "sdd-lifecycle",
    "sdd-brainstorm",
    "sdd-spec",
    "sdd-replan",
    "sdd-implement",
    "sdd-converge",
)

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_APPLYTO = re.compile(r'^applyTo:\s*"[^"]+"\s*$', re.MULTILINE)


def test_repo_wide_file_exists() -> None:
    assert _REPO_WIDE.is_file(), (
        ".github/copilot-instructions.md missing — run `make skills-sync`"
    )


def test_every_sdd_skill_has_a_pointer() -> None:
    for name in _SDD_SKILLS:
        p = _INSTRUCTIONS / f"{name}.instructions.md"
        assert p.is_file(), f"missing Copilot pointer: {p.relative_to(_AGENT_ROOT)}"


def test_pointers_resolve_to_canonical_skill() -> None:
    """FR-13: each pointer names an existing canonical SKILL.md."""
    for name in _SDD_SKILLS:
        body = (_INSTRUCTIONS / f"{name}.instructions.md").read_text()
        assert f"docs/skills/{name}/SKILL.md" in body, (
            f"{name}.instructions.md does not point at its canonical SKILL.md"
        )
        assert (_SKILLS / name / "SKILL.md").is_file(), (
            f"pointer target docs/skills/{name}/SKILL.md does not exist"
        )


def test_applyto_frontmatter_valid() -> None:
    """FR-14: valid applyTo glob frontmatter on every pointer."""
    for name in _SDD_SKILLS:
        text = (_INSTRUCTIONS / f"{name}.instructions.md").read_text()
        m = _FRONTMATTER.match(text)
        assert m, f"{name}.instructions.md has no --- frontmatter block ---"
        assert _APPLYTO.search(m.group(1)), (
            f'{name}.instructions.md lacks a valid applyTo: "<glob>" line'
        )


def test_pointers_are_thin() -> None:
    """FR-15: body is a pointer only — frontmatter + a single non-empty line."""
    for name in _SDD_SKILLS:
        text = (_INSTRUCTIONS / f"{name}.instructions.md").read_text()
        m = _FRONTMATTER.match(text)
        assert m, f"{name}.instructions.md has no frontmatter"
        body_lines = [ln for ln in m.group(2).splitlines() if ln.strip()]
        assert len(body_lines) <= 1, (
            f"{name}.instructions.md restates prose ({len(body_lines)} body lines) "
            "— pointers must stay thin (pointer + applyTo + 1 line):\n"
            + "\n".join(body_lines)
        )
