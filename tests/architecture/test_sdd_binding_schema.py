"""SDD workspace-binding schema↔reference completeness gate (spec FR-8).

The portable SDD skills resolve `{{placeholder}}` tokens from a workspace binding.
The vocabulary is declared once in ``docs/skills/_sdd/binding.schema.md`` (a
markdown table) and this repo's reference values live in
``docs/skills/_sdd/binding.reference.toml``. If the two drift — a key in one but
not the other — a skill would reference a placeholder with no reference value (or
carry a dead reference), so this test fails on any mismatch.

Governed by ADR-0032; realizes FR-8 of
``docs/plan/sdd-skills-portability-export.spec.md``.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parents[2]
_SDD = _AGENT_ROOT / "docs" / "skills" / "_sdd"
_SCHEMA = _SDD / "binding.schema.md"
_REFERENCE = _SDD / "binding.reference.toml"

# A schema-table row for a binding key looks like: ``| `constitution` | … |``.
# The optional [examples] section uses its own table; we only cross-check the
# 13-key core vocabulary, whose rows carry a fill-prompt as the last column.
_KEY_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|")


def _schema_keys() -> set[str]:
    keys: set[str] = set()
    in_vocab = False
    for line in _SCHEMA.read_text().splitlines():
        if line.startswith("## The vocabulary"):
            in_vocab = True
            continue
        if in_vocab and line.startswith("## "):
            break  # left the vocabulary section (e.g. into ## Optional examples)
        if in_vocab:
            m = _KEY_ROW.match(line)
            if m:
                keys.add(m.group(1))
    return keys


def _reference_keys() -> set[str]:
    data = tomllib.loads(_REFERENCE.read_text())
    return set(data.get("binding", {}).keys())


def test_schema_reference_complete() -> None:
    schema = _schema_keys()
    reference = _reference_keys()
    assert schema, "no binding keys parsed from binding.schema.md vocabulary table"
    missing_in_reference = schema - reference
    extra_in_reference = reference - schema
    assert not missing_in_reference and not extra_in_reference, (
        "binding.schema.md and binding.reference.toml drifted:\n"
        f"  declared in schema but missing from reference: {sorted(missing_in_reference)}\n"
        f"  in reference but not declared in schema: {sorted(extra_in_reference)}"
    )


def test_reference_covers_all_thirteen_keys() -> None:
    # The vocabulary is fixed at 13 keys (ADR-0032 / spec §4). A drift in the
    # count is itself a signal the contract changed without updating the spec.
    assert len(_reference_keys()) == 13, (
        f"expected 13 binding keys, found {len(_reference_keys())}: "
        f"{sorted(_reference_keys())}"
    )
