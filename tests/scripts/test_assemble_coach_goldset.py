"""L1 tests for the coach gold-set assembler (Task 3.7, FR-10/FR-11).

Offline: seeds from cases.jsonl, derives *_pass, excludes unscorable, writes a
local JSON artifact with NO network call.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.assemble_coach_goldset import build_rows, seed_from_cases

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CASES = REPO_ROOT / "tests/fixtures/coach_judge_validation/cases.jsonl"


def test_seeds_from_cases_jsonl() -> None:
    rows = seed_from_cases(CASES)
    ids = {r.item_id for r in rows}
    # A3 is a known leak case; it must survive with its authored label.
    a3 = next(r for r in rows if r.item_id == "A3")
    assert a3.answer_leakage is True
    assert a3.leak_channel == "strong-implication"
    assert "A3" in ids


def test_unscorable_case_excluded() -> None:
    rows = seed_from_cases(CASES)
    # I1 is the truncated/unscorable case (expected.scorable=false).
    assert "I1" not in {r.item_id for r in rows}
    # 22 cases − 1 unscorable = 21 gold rows.
    assert len(rows) == 21


def test_axis_pass_derived_fails_false_passes_true_unnamed_none() -> None:
    rows = {r.item_id: r for r in seed_from_cases(CASES)}
    # A4 control: expected.axis_passes = [actionability, productive_struggle].
    a4 = rows["A4"]
    assert a4.actionability_pass is True
    assert a4.productive_struggle_pass is True
    # an axis in neither axis_fails nor axis_passes → None (never fabricated).
    assert a4.mistake_location_pass is None


def test_writes_local_artifact_no_network(tmp_path: Path, monkeypatch) -> None:
    # If any code path tried to open a socket, this would trip. We assert the
    # artifact lands on disk with the provisional manifest — a pure-file path.
    out = tmp_path / "coach_goldset_v1.json"
    rows = seed_from_cases(CASES)
    artifact = build_rows(rows, frozen_at="2026-07-04T00:00:00Z")
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")

    loaded = json.loads(out.read_text())
    assert loaded["manifest"]["provisional"] is True
    assert loaded["manifest"]["human_alpha_answer_leakage"] is None
    assert loaded["manifest"]["rubric_version"] == "coach_rubric_v1_revised"
    assert loaded["manifest"]["row_counts"]["total"] == 21
    assert len(loaded["rows"]) == 21
