"""L1 Parity: the frontend dev-seed hint ladder mirrors the Python asset.

ADR-0014 accepted risk: two serving planes (frontend ``hint`` table seed,
backend persona render asset). The Python asset
(``components/subject_coach_hints.py::AUTHORED_RUNGS``) is the single source;
this test pins the ``_dev_seed.ts`` copy against it so drift is mechanical,
not a prose promise. Text-level check (no cross-language import): the TS file
is normalized (string-concat quotes stripped, whitespace collapsed) and every
authored rung body + id must appear.
"""

from __future__ import annotations

import re
from pathlib import Path

from components.subject_coach_hints import AUTHORED_RUNGS

_SEED = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend"
    / "lib"
    / "adapters"
    / "engine"
    / "_dev_seed.ts"
)


def _normalized_seed_text() -> str:
    text = _SEED.read_text(encoding="utf-8")
    # Collapse TS string concatenation: strip the double-quote delimiters and
    # '+' joins, then collapse whitespace. Rung bodies contain no '"'.
    text = text.replace('" +', " ").replace('"', " ")
    return re.sub(r"\s+", " ", text)


def _normalize(body: str) -> str:
    return re.sub(r"\s+", " ", body).strip()


class TestHintSeedParity:
    def test_every_authored_rung_body_is_in_the_dev_seed(self):
        seed = _normalized_seed_text()
        missing = [
            (r.question_id, r.rung)
            for r in AUTHORED_RUNGS
            if _normalize(r.body_md) not in seed
        ]
        assert not missing, (
            "dev-seed ladder drifted from components/subject_coach_hints.py "
            f"(missing {missing}) — regenerate DEV_HINTS from the Python asset"
        )

    def test_ladder_shape_matches(self):
        """18 rungs, 6 questions, exactly rungs 1..3 each — both planes."""
        assert len(AUTHORED_RUNGS) == 18
        seed = _normalized_seed_text()
        for rung in AUTHORED_RUNGS:
            assert f"devHint( {rung.question_id} , {rung.rung}," in seed, (
                f"seed missing devHint entry for ({rung.question_id}, {rung.rung})"
            )
