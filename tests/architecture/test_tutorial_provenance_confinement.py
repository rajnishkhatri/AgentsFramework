"""Architecture gate: a reviewed=true tutorial row carries earned provenance.

The tutorial-family sibling of ``test_hint_provenance_confinement`` (ADR-0028 /
E1a FR-2). ``reviewed = true`` is EARNED by a hand-authored + human-leak-checked
seed stamped ``hand:<author>@<date>``, or (scale-up) an LLM cascade stamped
``llm:<model>@<promptrev>``. A bare unstamped ``reviewed:true`` fails the build.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_SEED_DIR = _REPO / "frontend" / "lib" / "adapters" / "engine"

# hand:<author>@<date>  |  llm:<model>@<promptrev>
_LEGITIMATE = re.compile(r"^(?:hand|llm):[^@\s]+@[^@\s]+$")

# Every checked-in engine seed file that may carry tutorial rows.
_SEED_FILES = (
    "_dev_seed.ts",
    "_test01_english_corpus.ts",
    "_test_item_bank.ts",
    "_hint_bank.ts",
    "_lesson_seed.ts",
)


def _row_spans(source: str) -> list[str]:
    """Split source into per-object row candidates, anchored on ``"id"``.

    Each seed row is an object literal that opens with an ``"id"`` key; a row
    runs from one ``"id"`` up to the next (or end of source). This is
    order-independent within a row and unbounded in length, so a forged
    ``generated_from`` cannot escape by (a) preceding ``body_md`` or (b) hiding
    behind a very long ``body_md`` — the two evasions a fixed forward window
    from ``body_md`` missed.
    """
    starts = [m.start() for m in re.finditer(r'"id"\s*:', source)]
    if not starts:
        return []
    bounds = starts + [len(source)]
    return [source[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


def _reviewed_tutorial_provenances(source: str) -> list[str]:
    """Extract generated_from values from reviewed=true tutorial-family rows.

    Tutorial rows are discriminated by ``body_md`` + ``skill_id`` +
    ``generated_from`` (hint rows use ``generated_by`` + ``rung``; question
    rows use ``stem`` / ``stem_md``). Row-scoped: reviewed / generated_from are
    matched anywhere inside the same row object, regardless of field order or
    body length.
    """
    provenances: list[str] = []
    for row in _row_spans(source):
        # Must look like a tutorial: body_md + skill_id, generated_from (not
        # generated_by), and no rung (hints).
        if not re.search(r'"body_md"\s*:', row):
            continue
        if not re.search(r'"skill_id"\s*:', row):
            continue
        if re.search(r'"rung"\s*:', row):
            continue
        if not re.search(r'"generated_from"\s*:', row):
            continue
        reviewed = re.search(r'"reviewed"\s*:\s*true', row)
        gen = re.search(r'"generated_from"\s*:\s*"([^"]*)"', row)
        if reviewed and gen:
            provenances.append(gen.group(1))
    return provenances


def _is_legitimate(provenance: str) -> bool:
    return bool(_LEGITIMATE.match(provenance))


def test_no_seed_file_ships_a_reviewed_tutorial_without_earned_provenance() -> None:
    offenders: list[str] = []
    for name in _SEED_FILES:
        path = _SEED_DIR / name
        if not path.exists():
            continue
        for prov in _reviewed_tutorial_provenances(path.read_text(encoding="utf-8")):
            if not _is_legitimate(prov):
                offenders.append(f"{name}: reviewed tutorial generated_from={prov!r}")
    assert offenders == [], (
        "reviewed=true tutorial rows must carry 'hand:<author>@<date>' or "
        "'llm:<model>@<promptrev>' (ADR-0028 / E1a FR-2). "
        "Offenders: " + "; ".join(offenders)
    )


def test_detector_flags_a_self_stamped_reviewed_tutorial() -> None:
    """Red-first anchor: a hand-stamped reviewed tutorial row is caught."""
    sneaky = (
        '{ "id": "tut-1", "skill_id": "s-punc", '
        '"body_md": "Fence non-essential clauses.", '
        '"reviewed": true, "generated_from": "forged-stamp" }'
    )
    provs = _reviewed_tutorial_provenances(sneaky)
    assert provs == ["forged-stamp"]
    assert not _is_legitimate(provs[0])


def test_detector_flags_a_row_ordering_provenance_before_body_md() -> None:
    """Evasion E: reviewed/generated_from emitted BEFORE body_md must not escape
    a forward-only window. Row-scoped scan catches it."""
    sneaky = (
        '{ "id": "tut-e", "skill_id": "s-punc", '
        '"reviewed": true, "generated_from": "forged-before", '
        '"body_md": "Fence non-essential clauses." }'
    )
    provs = _reviewed_tutorial_provenances(sneaky)
    assert provs == ["forged-before"]
    assert not _is_legitimate(provs[0])


def test_detector_flags_a_row_with_a_long_body_md() -> None:
    """Evasion F: a body_md longer than any fixed window must not push
    generated_from out of scan range. Row-scoped scan catches it."""
    long_body = "x" * 4000
    sneaky = (
        '{ "id": "tut-f", "skill_id": "s-punc", '
        f'"body_md": "{long_body}", '
        '"reviewed": true, "generated_from": "forged-long" }'
    )
    provs = _reviewed_tutorial_provenances(sneaky)
    assert provs == ["forged-long"]
    assert not _is_legitimate(provs[0])


def test_committed_lesson_seed_rows_are_actually_scanned() -> None:
    """Guard the guard: the lesson seed's rows must be VISIBLE to the detector."""
    bank = _SEED_DIR / "_lesson_seed.ts"
    assert bank.exists(), "committed lesson seed missing (_lesson_seed.ts)"
    provs = _reviewed_tutorial_provenances(bank.read_text(encoding="utf-8"))
    assert len(provs) >= 1, (
        f"expected the lesson seed's reviewed rows to be visible "
        f"(got {len(provs)}) — did the seed format drift from JSON-quoted keys?"
    )
    assert all(_is_legitimate(p) for p in provs), provs
