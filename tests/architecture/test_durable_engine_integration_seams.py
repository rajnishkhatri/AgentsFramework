"""T R.9 — focused integration tests must exist for core production seams.

Finding 9 / §8: close-route tally + pointer clear, coarse summary hydration,
migrate_engine replay/rollback, and real-Postgres insertAttempt were untested.
This gate keeps those four seams in the suite (a–c in-gate; d on-demand).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_FE = _REPO / "frontend"

_CLOSE = _FE / "app/api/engine/session/close/route.test.ts"
_SUMMARY = _FE / "app/api/engine/summary/route.test.ts"
_MIGRATE = _FE / "scripts/migrate_engine.integration.test.ts"
_INSERT = _FE / "lib/adapters/engine/db/pg_insert_attempt.integration.test.ts"


@pytest.mark.parametrize(
    ("path", "needles"),
    [
        (
            _CLOSE,
            (
                "setSessionCurrentQuestion",
                "commitFirstTally",
                "patchSessionClose",
                "score_correct",
            ),
        ),
        (
            _SUMMARY,
            (
                "GET /api/engine/summary",
                "skillTaxonomy",
                "listSessionAttempts",
                "miss_questions",
            ),
        ),
        (
            _MIGRATE,
            (
                "migrate_engine",
                "skipped",
                "seed_",
                "ROLLBACK",
                "_frontend_migrations",
            ),
        ),
        (
            _INSERT,
            (
                "insertAttempt",
                "already-existed",
                "pgEngineDbFrom",
                "skipIf",
            ),
        ),
    ],
    ids=["close", "summary", "migrate", "insertAttempt"],
)
def test_r9_integration_seam_file_exists_with_contract(
    path: Path, needles: tuple[str, ...]
) -> None:
    assert path.is_file(), f"T R.9 missing integration test: {path.relative_to(_REPO)}"
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{path.name} must cover `{needle}` (T R.9)"
