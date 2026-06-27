"""Deterministic workspace fixtures for the model-A/B GEN-L1 answer corpus.

The GEN-L1 prompts (frontend/e2e/fixtures/model_ab_corpus.json) reference files
under ``/workspace/…``; the batch runner rewrites that prefix to ``<repo>/
workspace/`` (run_goaljudge_synthetic_batch._normalize_prompt_for_batch) and the
file-IO tool sandboxes to ``WORKSPACE_DIR``. Without the files present, every
L1 file-task is a guaranteed FAIL (the A3a finding, design doc §6 RC4) — measuring
"model on an impossible task," not answer quality.

This module seeds each referenced file with KNOWN content so the model-A/B answer
scorer (scripts/model_ab_answer_score.py) can grade the model's output against a
deterministic expected value. The `EXPECTED` table is the single source of truth
linking each case → its correct answer; the seed and the scorer both read it.

Idempotent: every call overwrites, so a sweep is reproducible. Machine-independent:
writes under the passed ``workspace`` dir (default ``<repo>/workspace``), not the
literal ``/workspace`` OS root.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACE = AGENT_ROOT / "workspace"


@dataclass(frozen=True)
class ExpectedAnswer:
    """The deterministic answer the seeded fixtures imply for one L1 case.

    ``kind`` drives the scorer's match strategy:
      - "numeric"  : parse the model's answer for a number, compare to ``value``
                     within ``tol`` (covers int + 1-decimal-rounded floats).
      - "substring": the model's answer must CONTAIN ``value`` (case-insensitive).
                     Use for tokens/words/names where surrounding prose is fine.
    """

    case: str
    kind: str  # "numeric" | "substring"
    value: str  # canonical expected (string; numeric parsed by scorer)
    tol: float = 0.0  # numeric tolerance (0.05 covers 1-decimal rounding)


# ── The fixtures + the answers they imply (ONE source of truth) ──────────────
# Each seeder returns nothing; it writes its file(s) under ``ws``. The EXPECTED
# row below it records the answer those exact contents produce.


def _seed(ws: Path) -> None:
    (ws / "nums").mkdir(parents=True, exist_ok=True)
    # 01 read-sum: 7 + 12 + 23 = 42
    (ws / "nums" / "a.txt").write_text("7\n")
    (ws / "nums" / "b.txt").write_text("12\n")
    (ws / "nums" / "c.txt").write_text("23\n")
    # 02 lookup-format: domain after @ = example.com
    (ws / "contact.txt").write_text(
        "Name: Dana Lee\nEmail: dana.lee@example.com\nPhone: 555-0142\n"
    )
    # 03 count-lines: 4 non-empty lines (blank lines interleaved)
    (ws / "log.txt").write_text(
        "first line\n\nsecond line\nthird line\n\n\nfourth line\n"
    )
    # 04 pick-max: highest score -> Priya
    (ws / "scores.csv").write_text(
        "name,score\nAlex,71\nPriya,93\nJordanK,88\nSam,64\n"
    )
    # 05 convert-unit: 5 miles -> 8.0467 km -> rounded 1dp = 8.0
    (ws / "distance.txt").write_text("5\n")
    # 06 write-readback: the model WRITES status.txt then reads it. We don't
    #    pre-seed it (the task is to create it); the expected final answer
    #    confirms the word "ready".
    # 13 extract-field: profile.json name = Morgan Avery
    (ws / "profile.json").write_text(
        json.dumps({"name": "Morgan Avery", "role": "engineer", "id": 7}) + "\n"
    )
    # 14 sort-list: sorted alphabetically -> apple, banana, cherry, date
    (ws / "words.txt").write_text("cherry\nbanana\ndate\napple\n")
    # 15 bool-check: 17 -> odd
    (ws / "n.txt").write_text("17\n")
    # 16 first-match: first line containing 'denied'
    (ws / "access.log").write_text(
        "GET /home 200 allowed\n"
        "POST /admin 403 denied for user bob\n"
        "GET /x 200 allowed\n"
        "DELETE /y 403 denied for user carol\n"
    )


EXPECTED: tuple[ExpectedAnswer, ...] = (
    ExpectedAnswer("GEN-L1-read-sum-01", "numeric", "42"),
    ExpectedAnswer("GEN-L1-lookup-format-02", "substring", "example.com"),
    ExpectedAnswer("GEN-L1-count-lines-03", "numeric", "4"),
    ExpectedAnswer("GEN-L1-pick-max-04", "substring", "Priya"),
    # 5 mi * 1.60934 = 8.0467 -> 1dp = 8.0; tol absorbs a model that reports the
    # unrounded 8.05/8.047 (and FP noise at the 0.05 boundary).
    ExpectedAnswer("GEN-L1-convert-unit-05", "numeric", "8.0", tol=0.1),
    ExpectedAnswer("GEN-L1-write-readback-06", "substring", "ready"),
    ExpectedAnswer("GEN-L1-extract-field-13", "substring", "Morgan Avery"),
    # sorted words — score each token's presence in order via substring on the
    # joined canonical; the scorer treats comma/space-insensitively.
    ExpectedAnswer("GEN-L1-sort-list-14", "substring", "apple, banana, cherry, date"),
    ExpectedAnswer("GEN-L1-bool-check-15", "substring", "odd"),
    ExpectedAnswer("GEN-L1-first-match-16", "substring", "denied for user bob"),
)

EXPECTED_BY_CASE: dict[str, ExpectedAnswer] = {e.case: e for e in EXPECTED}


def seed_workspace(workspace: Path | None = None) -> Path:
    """Write all GEN-L1 fixtures under ``workspace`` (default <repo>/workspace).

    Returns the workspace path. Idempotent (overwrites)."""
    ws = workspace or DEFAULT_WORKSPACE
    ws.mkdir(parents=True, exist_ok=True)
    _seed(ws)
    return ws


if __name__ == "__main__":
    import sys

    ws = seed_workspace(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    files = sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*") if p.is_file())
    print(f"seeded {len(EXPECTED)} GEN-L1 expectations under {ws}")
    for f in files:
        print("  ", f)
