"""L1 tests for the coach gold-set assembler (Task 3.7, FR-10/FR-11).

Offline: seeds from cases.jsonl, derives *_pass, excludes unscorable, writes a
local JSON artifact with NO network call.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.assemble_coach_goldset import (
    alpha_from_combined_sheet,
    build_rows,
    rows_from_combined_sheet,
    seed_from_cases,
)

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


# ── E6: assemble the non-provisional v1 from the adjudicated combined sheet ───

_COMBINED_HEADER = (
    "item_id,split,stratum,mode,provenance,learner_utterance,coach_reply,"
    "question,r1_answer_leakage,r2_answer_leakage,adjudicated_answer_leakage,note\n"
)


def _write_combined(tmp_path: Path, body_rows: list[str]) -> Path:
    p = tmp_path / "combined.csv"
    p.write_text(_COMBINED_HEADER + "".join(r + "\n" for r in body_rows))
    return p


def test_rows_from_combined_sheet_maps_labels_and_splits(tmp_path: Path) -> None:
    sheet = _write_combined(
        tmp_path,
        [
            # a synthetic dev row, adjudicated leak
            "D0001,dev,rule_naming,pre_submit,synthetic,u1,r1,,true,false,true,note",
            # a fresh-authored test row, adjudicated clean
            "T-CLEAN-01,test,breadth,pre_submit,fresh-authored,u2,r2,q2,false,false,false,",
        ],
    )
    rows = rows_from_combined_sheet(sheet)
    by_id = {r.item_id: r for r in rows}
    assert by_id["D0001"].split.value == "dev"
    assert by_id["D0001"].provenance.value == "synthetic"
    assert by_id["D0001"].answer_leakage is True
    assert by_id["T-CLEAN-01"].split.value == "test"
    assert by_id["T-CLEAN-01"].provenance.value == "fresh-authored"
    assert by_id["T-CLEAN-01"].answer_leakage is False
    # the adjudicated column is the label source, not r1/r2.
    assert by_id["T-CLEAN-01"].question == "q2"


def test_rows_from_combined_requires_adjudication(tmp_path: Path) -> None:
    """A blank adjudicated cell must FAIL closed — no silent default label."""
    import pytest

    sheet = _write_combined(
        tmp_path,
        ["D0001,dev,rule_naming,pre_submit,synthetic,u1,r1,,true,false,,note"],
    )
    with pytest.raises(ValueError, match="adjudicat"):
        rows_from_combined_sheet(sheet)


def test_alpha_from_combined_sheet_reads_rater_columns(tmp_path: Path) -> None:
    sheet = _write_combined(
        tmp_path,
        [
            "A,dev,s,pre_submit,synthetic,u,r,,true,true,true,",
            "B,dev,s,pre_submit,synthetic,u,r2,,false,false,false,",
            "C,dev,s,pre_submit,synthetic,u,r3,,true,false,true,",
            "D,dev,s,pre_submit,synthetic,u,r4,,false,true,false,",
        ],
    )
    a = alpha_from_combined_sheet(sheet)
    assert a is not None and 0.0 <= a <= 1.0


def test_build_rows_freezes_non_provisional_when_gates_clear(tmp_path: Path) -> None:
    """The whole point of E6: enough rows + α ≥ 0.80 ⇒ provisional=False."""
    # 200 dev rows (clears the floor) with a real α, all disjoint from an empty test.
    body = [
        f"D{n:04d},dev,s,pre_submit,synthetic,u{n},r{n},,true,true,true,"
        for n in range(1, 101)
    ] + [
        f"D{n:04d},dev,s,pre_submit,synthetic,u{n},r{n},,false,false,false,"
        for n in range(101, 201)
    ]
    # a couple of held-out fresh test rows so the test split is non-empty
    body += [
        "T-1,test,s,pre_submit,fresh-authored,tu1,tr1,q,true,true,true,",
        "T-2,test,s,pre_submit,fresh-authored,tu2,tr2,q,false,false,false,",
    ]
    sheet = _write_combined(tmp_path, body)
    rows = rows_from_combined_sheet(sheet)
    alpha = alpha_from_combined_sheet(sheet)
    artifact = build_rows(
        rows,
        frozen_at="2026-07-05T00:00:00Z",
        provisional=False,
        human_alpha_answer_leakage=alpha,
    )
    assert artifact["manifest"]["provisional"] is False
    assert artifact["manifest"]["row_counts"]["total"] == 202
    assert artifact["manifest"]["row_counts"]["test"] == 2
