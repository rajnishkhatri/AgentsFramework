"""Bank-seed pre-flight validators (D3 spec FR-1 / FR-2 / FR-8).

Pure, offline checks run over the authored seed BEFORE a promotion run burns
LLM calls: every violation message NAMES the offending row (index + stem
snippet) so authoring errors are one-glance fixable. Fail-closed posture —
an unknown ``standard_id``, a difficulty outside the standard's syllabus
bands, a ``skill_id`` contradicting the standard's app-skill mapping, or the
retired pre-D3 ``topic`` key each produce a violation; promotion never
repairs or defaults a tag (FR-5).

Consumed by `tests/scripts/test_bank_seed_preflight.py` (the CI gate; Phase
B's T2 adds the schema + matrix-conformance sections there). Stdlib only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
CANONICAL_SEED = _REPO / "docs" / "plan" / "coach-item-bank-live.seed.json"
CANONICAL_SYLLABUS = _REPO / "docs" / "plan" / "act-english-syllabus.seed.json"


def load_seed_rows(path: Path = CANONICAL_SEED) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_syllabus(path: Path = CANONICAL_SYLLABUS) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _row_name(index: int, row: Mapping[str, Any]) -> str:
    stem = str(row.get("stem_md", "")).strip()
    return f"row {index} ({stem[:48]!r})"


def seed_tag_violations(
    rows: Sequence[Mapping[str, Any]], syllabus: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Tag-integrity violations for authored seed rows. Untagged rows pass —
    requiredness is the matrix-conformance section's concern (Phase B T2)."""
    standards = {int(s["standard_id"]): s for s in syllabus}
    violations: list[str] = []
    for index, row in enumerate(rows):
        name = _row_name(index, row)
        if "topic" in row:
            violations.append(
                f"{name}: retired 'topic' key — D3 renamed it to standard_id "
                "(one rename, no dual-field era)"
            )
        if "standard_id" not in row:
            continue
        sid = row["standard_id"]
        standard = standards.get(sid) if isinstance(sid, int) else None
        if standard is None:
            violations.append(
                f"{name}: unknown standard_id {sid!r} — not in the canonical syllabus"
            )
            continue
        difficulty = row.get("difficulty")
        if difficulty not in standard["bands"]:
            violations.append(
                f"{name}: difficulty {difficulty!r} outside standard {sid}'s "
                f"syllabus bands {standard['bands']}"
            )
        if row.get("skill_id") != standard["app_skill"]:
            violations.append(
                f"{name}: skill_id {row.get('skill_id')!r} contradicts standard "
                f"{sid}'s app skill {standard['app_skill']!r}"
            )
    return violations
