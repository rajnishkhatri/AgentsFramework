"""Architecture gate: a reviewed=true hint row is cascade-earned or authored.

The hint-family sibling of ``test_test_item_provenance_confinement`` — that
scan keys on ``stem_md`` (the exam-item discriminator) and is structurally
blind to hint rows, so the committed hint bank (coach-bank-hints spec FR-E2)
would ship unguarded without this file. Same posture as ADR-0015 clause 6 /
ADR-0014 clause 4: ``reviewed = true`` is EARNED by the verifier cascade
(``components/hint_generation.py`` — provenance ``"<model>@<run_id>"``) or
seeded from the human-leak-checked authored ladder (provenance ``"authored"``,
ADR-0014's legitimate non-cascade producer). A hand-edited or
migration-written reviewed hint row carries neither and fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
_SEED_DIR = _REPO / "frontend" / "lib" / "adapters" / "engine"

_CASCADE_PROVENANCE = re.compile(r"^[^@\s]+@[^@\s]+$")
_AUTHORED = "authored"

# Every checked-in engine seed file that may carry hint rows. _hint_bank.ts is
# the committed cascade-earned bank this gate exists for.
_SEED_FILES = (
    "_dev_seed.ts",
    "_test01_english_corpus.ts",
    "_test_item_bank.ts",
    "_hint_bank.ts",
)


def _reviewed_hint_provenances(source: str) -> list[str]:
    """Extract generated_by values from reviewed=true hint-family rows.

    Hint rows are discriminated by ``body_md`` + ``rung`` (question rows carry
    ``stem``, test_item rows ``stem_md`` — neither has ``body_md``). The
    emitted row order (id, subject, question_id, rung, body_md, reviewed,
    generated_by) puts reviewed/generated_by within a short window after
    body_md; 800 chars leaves ample headroom over the longest emitted body.
    """
    provenances: list[str] = []
    for m in re.finditer(r'"body_md"\s*:', source):
        window = source[m.start() : m.start() + 800]
        if not re.search(
            r'"rung"\s*:', source[max(0, m.start() - 200) : m.start() + 800]
        ):
            continue
        reviewed = re.search(r'"reviewed"\s*:\s*true', window)
        gen = re.search(r'"generated_by"\s*:\s*"([^"]*)"', window)
        if reviewed and gen:
            provenances.append(gen.group(1))
    return provenances


def _is_legitimate(provenance: str) -> bool:
    return provenance == _AUTHORED or bool(_CASCADE_PROVENANCE.match(provenance))


def test_no_seed_file_ships_a_reviewed_hint_without_earned_provenance() -> None:
    offenders: list[str] = []
    for name in _SEED_FILES:
        path = _SEED_DIR / name
        if not path.exists():
            continue
        for prov in _reviewed_hint_provenances(path.read_text(encoding="utf-8")):
            if not _is_legitimate(prov):
                offenders.append(f"{name}: reviewed hint generated_by={prov!r}")
    assert offenders == [], (
        "reviewed=true hint rows must carry '<model>@<run_id>' cascade "
        "provenance or 'authored' (ADR-0014 clause 4 / spec FR-E2). "
        "Offenders: " + "; ".join(offenders)
    )


def test_detector_flags_a_self_stamped_reviewed_hint() -> None:
    """Red-first anchor: a hand-stamped reviewed hint row is caught."""
    sneaky = (
        '{ "id": "h-1", "question_id": "ti-gen-x", "rung": 2, '
        '"body_md": "psst it is B", "reviewed": true, '
        '"generated_by": "hand-edit" }'
    )
    provs = _reviewed_hint_provenances(sneaky)
    assert provs == ["hand-edit"]
    assert not _is_legitimate(provs[0])


def test_committed_hint_bank_rows_are_actually_scanned() -> None:
    """Guard the guard: the committed bank's rows must be VISIBLE to the
    detector (a seed-format drift would otherwise pass vacuously), and every
    one must carry earned provenance."""
    bank = _SEED_DIR / "_hint_bank.ts"
    assert bank.exists(), "committed hint bank missing (_hint_bank.ts)"
    provs = _reviewed_hint_provenances(bank.read_text(encoding="utf-8"))
    assert len(provs) >= 24, (
        f"expected the committed hint bank's reviewed rows to be visible "
        f"(got {len(provs)}) — did the seed format drift from JSON-quoted keys?"
    )
    assert all(_is_legitimate(p) for p in provs), provs
