"""Portable-core guards for the six SDD lifecycle skills (spec FR-1/3/4).

The SDD skills must be workspace-neutral: their canonical bodies express every
this-repo binding as a ``{{placeholder}}`` from the fixed vocabulary, never a
hard-coded token like ``AGENTS.md`` or ``make check``. Concrete values are
resolved at runtime from the workspace binding (``binding.reference.toml`` here).

Three guards:
  * ``test_no_repo_binding_token_leaks`` (FR-1) — no this-repo token in a body.
  * ``test_reference_binding_round_trips`` (FR-3) — substituting the reference
    binding reproduces the strings the skills carried before the rewrite.
  * ``test_portable_skeleton_preserved`` (FR-4) — the portable methodology
    (10-stage table, micro-loop, EARS, red/green) survives, repo-agnostic.

Governed by ADR-0032; realizes FR-1/FR-3/FR-4 of
``docs/plan/sdd-skills-portability-export.spec.md``.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_SKILLS = _AGENT_ROOT / "docs" / "skills"
_REFERENCE = _SKILLS / "_sdd" / "binding.reference.toml"

_SDD_SKILLS = (
    "sdd-lifecycle",
    "sdd-brainstorm",
    "sdd-spec",
    "sdd-replan",
    "sdd-implement",
    "sdd-converge",
)

# The exact this-repo binding TOKENS the portable body must not contain (spec §4).
# Keyed on literal tokens, not English words, so a skill discussing "the
# constitution" generically does not false-positive (spec §6).
_FORBIDDEN_TOKENS = (
    "AGENTS.md",
    "make check",
    "pytest tests/architecture/",
    "docs/adr/",
    "docs/plan/",
    "eval_capture",
    "scripts/hooks/",
    "ADR-OK:",
    "G8-OK:",
    "sdd_lifecycle_runbook.md",
    "ai-slop-backpressure",
    "components/router.py",
    "services/guardrails.py",
    "middleware/app_prod.py",
    "agent_ui_adapter/server.py",
)


def _skill_body(name: str) -> str:
    return (_SKILLS / name / "SKILL.md").read_text()


def test_no_repo_binding_token_leaks() -> None:
    leaks: list[str] = []
    for name in _SDD_SKILLS:
        body = _skill_body(name)
        for lineno, line in enumerate(body.splitlines(), start=1):
            # Strip {{placeholder}} spans first: a binding token may legitimately
            # appear *inside* a placeholder name (e.g. {{examples.eval_capture_rule}}
            # contains "eval_capture"). Only a token in the surrounding prose is a
            # real hard-coded leak.
            outside = re.sub(r"\{\{[^}]*\}\}", "", line)
            for token in _FORBIDDEN_TOKENS:
                if token in outside:
                    leaks.append(f"{name}/SKILL.md:{lineno}: leaked token {token!r}")
    assert not leaks, (
        "portable SDD skill bodies must not hard-code this-repo binding tokens "
        "— use a {{placeholder}} resolved from the workspace binding:\n"
        + "\n".join(leaks)
    )


def _reference_binding() -> dict[str, str]:
    data = tomllib.loads(_REFERENCE.read_text())
    return {**data.get("binding", {}), **data.get("examples", {})}


# Map each forbidden token to the placeholder that should replace it, so we can
# prove the reference binding round-trips (FR-3): resolving the placeholders in a
# body must be able to reproduce the original tokens.
_TOKEN_TO_KEY = {
    "AGENTS.md": "constitution",
    "make check": "check_gate",
    "pytest tests/architecture/ -q": "test_gate",
    "docs/adr/0000-template.md": "adr_template",
    "docs/adr/decisions.md": "decision_log",
    "docs/adr/GATES.md": "gate_catalog",
    "docs/adr/": "adr_home",
    "docs/plan/": "plan_home",
    "sdd_lifecycle_runbook.md": "methodology_source",
    "ADR-OK:": "adr_waiver_token",
    "G8-OK:": "test_waiver_token",
}


def test_reference_binding_round_trips() -> None:
    binding = _reference_binding()
    # Every placeholder the bodies use must have a reference value, and every
    # token→key mapping must resolve to a value that actually contains the token
    # (so a this-repo reader sees the original string).
    used = set()
    for name in _SDD_SKILLS:
        used |= set(re.findall(r"\{\{([a-z_]+)\}\}", _skill_body(name)))
    # "placeholder" is the meta-word in the binding preamble ("resolve each
    # {{placeholder}}"), not a binding key — exclude it from the resolution check.
    used.discard("placeholder")
    unbound = sorted(k for k in used if k not in binding)
    assert not unbound, (
        f"placeholders used in skill bodies with no reference value: {unbound}"
    )
    for token, key in _TOKEN_TO_KEY.items():
        assert key in binding, f"round-trip key {key!r} absent from reference binding"
        assert token in binding[key], (
            f"reference[{key!r}]={binding[key]!r} does not reproduce token {token!r}"
        )


# Markers the ROUTER skill (sdd-lifecycle) actually owns: the five stage-owner
# skills + the human↔agent micro-loop. EARS is owned by sdd-spec, not the router,
# so it is asserted there, not here.
_SKELETON_MARKERS = (
    "sdd-brainstorm",
    "sdd-spec",
    "sdd-replan",
    "sdd-implement",
    "sdd-converge",
    "micro-loop",
)


def test_portable_skeleton_preserved() -> None:
    # The router (sdd-lifecycle) must still name the portable stage skeleton.
    body = _skill_body("sdd-lifecycle").lower()
    missing = [m for m in _SKELETON_MARKERS if m.lower() not in body]
    assert not missing, f"sdd-lifecycle lost portable-methodology markers: {missing}"
    # EARS is the spec skill's portable notation — assert it survived there.
    assert "ears" in _skill_body("sdd-spec").lower(), (
        "sdd-spec lost the portable EARS notation"
    )
