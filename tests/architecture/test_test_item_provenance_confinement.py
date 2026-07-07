"""Architecture gate: a reviewed=true test_item row is earned in the cascade only.

ADR-0015 §Consequences mandates this code-enforced backstop for "`reviewed=true`
is earned in the Python cascade only" (the ADR-0011 lesson: a prose-only
integrity claim rots). It works *because* the cascade + importer re-stamp
provenance (ADR-0015 clause 6): a passing item carries
``generated_by="<model>@<run_id>"``, so a hand-authored or migration-written
``reviewed=true`` ``test_item`` row would carry a non-conforming ``generated_by``
and fail here.

Scope: every checked-in engine seed file. A ``reviewed=true`` row whose
``generated_by`` is NOT the ``<model>@<run_id>`` cascade format fails — for the
``test_item`` family only (the ``question``/``hint`` families keep their
legitimate non-cascade producers ``dev-seed``/``authored``). Today the governed
bank ships no committed reviewed seed (it is populated by the on-demand
generator), so this gate asserts the invariant is READY and unviolated, not that
rows exist.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_SEED_DIR = _REPO / "frontend" / "lib" / "adapters" / "engine"

# "<model>@<run_id>" — a non-empty model, then '@', then a non-empty run id.
_CASCADE_PROVENANCE = re.compile(r"^[^@\s]+@[^@\s]+$")

# The seed files the frontend composition inserts at build time.
# _test_item_bank.ts (ADR-0021) is the committed cascade-promoted bank — the
# first seed that actually SHIPS reviewed test_item rows, so it is exactly the
# file this gate exists for.
_SEED_FILES = ("_dev_seed.ts", "_test01_english_corpus.ts", "_test_item_bank.ts")


def _reviewed_test_item_provenances(source: str) -> list[str]:
    """Extract generated_by values from any reviewed=true test_item-family rows.

    A deliberately narrow textual scan (the seed files are generated TS data
    literals, not runtime code): find objects that look like test_item rows
    (carry stem_md, the exam-item discriminator that question/hint rows lack)
    AND reviewed:true, and pull their generated_by. Question/hint rows carry
    `stem`/`body_md`, never `stem_md`, so they are not matched.
    """
    provenances: list[str] = []
    # Split on object boundaries is brittle; instead find each stem_md-bearing
    # block and inspect a window around it. Window sized for the ADR-0021
    # extended row (teaching payload pushes reviewed/generated_by ~1.5k chars
    # past stem_md; measured max 1466 in the committed bank — 4000 leaves
    # headroom, and first-match semantics keep the window row-safe since a
    # row's own reviewed/generated_by precede the next row's).
    for m in re.finditer(r'"stem_md"\s*:', source):
        window = source[m.start() : m.start() + 4000]
        reviewed = re.search(r'"reviewed"\s*:\s*true', window)
        gen = re.search(r'"generated_by"\s*:\s*"([^"]*)"', window)
        if reviewed and gen:
            provenances.append(gen.group(1))
    return provenances


def test_no_seed_file_ships_a_reviewed_test_item_without_cascade_provenance() -> None:
    offenders: list[str] = []
    for name in _SEED_FILES:
        path = _SEED_DIR / name
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        for prov in _reviewed_test_item_provenances(source):
            if not _CASCADE_PROVENANCE.match(prov):
                offenders.append(f"{name}: reviewed test_item generated_by={prov!r}")
    assert offenders == [], (
        "reviewed=true test_item rows must carry a '<model>@<run_id>' cascade "
        "provenance (ADR-0015 clause 6 / write-confinement). Offenders: "
        + "; ".join(offenders)
    )


def test_detector_flags_a_self_stamped_reviewed_test_item() -> None:
    """The detector itself must catch the thing it guards (a red-first anchor):
    a reviewed=true test_item with a non-cascade generated_by is flagged."""
    sneaky = '{ "stem_md": "x", "reviewed": true, "generated_by": "test01-import" }'
    provs = _reviewed_test_item_provenances(sneaky)
    assert provs == ["test01-import"]
    assert not _CASCADE_PROVENANCE.match(provs[0])


def test_committed_bank_rows_are_actually_scanned() -> None:
    """ADR-0021: `_test_item_bank.ts` is the first committed reviewed seed.
    Guard the guard — the detector must EXTRACT its rows (a format drift that
    blinds the textual scan would otherwise pass vacuously), and every one
    must carry cascade provenance."""
    bank = _SEED_DIR / "_test_item_bank.ts"
    assert bank.exists(), "committed bank seed missing (_test_item_bank.ts)"
    provs = _reviewed_test_item_provenances(bank.read_text(encoding="utf-8"))
    assert len(provs) >= 6, (
        f"expected the committed bank's reviewed rows to be visible to the "
        f"detector (got {len(provs)}) — did the seed format drift from "
        f"JSON-quoted keys?"
    )
    assert all(_CASCADE_PROVENANCE.match(p) for p in provs), provs
