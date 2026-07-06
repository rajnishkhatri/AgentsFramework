"""Task 3.7c — the coach gold-set IAA double-label scaffold (deterministic).

Two thin CLIs, red-first:

* ``export_coach_goldset_iaa_sheets`` — provisional ``coach_goldset_v1`` fixture
  → two BLIND annotator sheets (item context, empty ``rN_answer_leakage``, and
  crucially NOT the provisional leak guess) + one combined sheet skeleton.
* ``compute_coach_goldset_alpha`` — a filled combined sheet → Krippendorff α on
  ``answer_leakage`` via ``services.governance.iaa`` (NaN→None, never 0.0).

No LLM, no network — pure CSV/JSON transforms, so these run in ``make check``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.compute_coach_goldset_alpha import alpha_from_combined_rows
from scripts.export_coach_goldset_iaa_sheets import build_sheets, join_dev_and_test

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "coach_goldset"
    / "coach_goldset_v1.json"
)


def _rows() -> list[dict]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["rows"]


# ── export: blind sheets ─────────────────────────────────────────────────────


def test_export_yields_one_row_per_item_in_each_sheet():
    rows = _rows()
    a1, a2, combined = build_sheets(rows)
    ids = {r["item_id"] for r in rows}
    assert {r["item_id"] for r in a1} == ids
    assert {r["item_id"] for r in a2} == ids
    assert {r["item_id"] for r in combined} == ids


def test_annotator_sheets_are_blind_no_leak_guess_leaked():
    """The provisional ``answer_leakage`` guess MUST NOT appear in an annotator
    sheet under any column — labeling has to be blind (mirrors GoalJudge)."""
    rows = _rows()
    a1, a2, _ = build_sheets(rows)
    for sheet in (a1, a2):
        for r in sheet:
            assert "answer_leakage" not in r  # no bare provisional guess
            # the rater's own label column exists and starts empty
            assert any(k.endswith("_answer_leakage") for k in r)
    # r1 sheet carries r1's column, not r2's, and vice-versa
    assert all("r1_answer_leakage" in r and r["r1_answer_leakage"] == "" for r in a1)
    assert all("r2_answer_leakage" in r and r["r2_answer_leakage"] == "" for r in a2)


def test_annotator_sheets_carry_item_context():
    """Blind ≠ contextless: the rater needs the reply + item to apply the
    options-still-live test."""
    rows = _rows()
    a1, _, _ = build_sheets(rows)
    for r in a1:
        for col in ("learner_utterance", "coach_reply", "question", "mode"):
            assert col in r


# ── alpha: recomputable from the combined sheet ──────────────────────────────


def test_alpha_perfect_agreement_is_one():
    combined = [
        {"item_id": "A", "r1_answer_leakage": "true", "r2_answer_leakage": "true"},
        {"item_id": "B", "r1_answer_leakage": "false", "r2_answer_leakage": "false"},
        {"item_id": "C", "r1_answer_leakage": "true", "r2_answer_leakage": "true"},
    ]
    assert alpha_from_combined_rows(combined) == 1.0


def test_alpha_none_when_underdefined_not_zero():
    """AP-6: an empty / single-class sheet is NaN→None, never a fake 0.0."""
    empty: list[dict] = []
    assert alpha_from_combined_rows(empty) is None
    single_class = [
        {"item_id": "A", "r1_answer_leakage": "false", "r2_answer_leakage": "false"},
    ]
    # only one nominal class overall → under-defined → None
    assert alpha_from_combined_rows(single_class) is None


def test_alpha_below_one_on_disagreement():
    combined = [
        {"item_id": "A", "r1_answer_leakage": "true", "r2_answer_leakage": "false"},
        {"item_id": "B", "r1_answer_leakage": "false", "r2_answer_leakage": "true"},
        {"item_id": "C", "r1_answer_leakage": "true", "r2_answer_leakage": "true"},
        {"item_id": "D", "r1_answer_leakage": "false", "r2_answer_leakage": "false"},
    ]
    a = alpha_from_combined_rows(combined)
    assert a is not None and a < 1.0


# ── alpha: label-integrity failure paths (TAP-4 — malformed input must SURFACE) ─


def test_malformed_label_is_not_coerced_and_lowers_agreement():
    """A typo'd label ("ture", "MAYBE") must NOT be silently coerced to
    true/false — it becomes its own nominal class, which DEPRESSES α so a human
    sees the error, rather than being folded into a real class and hidden. This
    locks the ``normalize_bool_label`` contract (its docstring: 'never silently
    coerce maybe to true or false'); coercing instead would corrupt the gate the
    re-cert reads."""
    from scripts.compute_coach_goldset_alpha import normalize_bool_label

    # not coerced: the typo passes through as a distinct token
    assert normalize_bool_label("ture") == "ture"
    assert normalize_bool_label("maybe") == "maybe"
    # and it drags agreement below what the same rows score when clean
    typo = [
        {"item_id": "A", "r1_answer_leakage": "ture", "r2_answer_leakage": "true"},
        {"item_id": "B", "r1_answer_leakage": "false", "r2_answer_leakage": "false"},
        {"item_id": "C", "r1_answer_leakage": "true", "r2_answer_leakage": "true"},
    ]
    clean = [dict(r) for r in typo]
    clean[0]["r1_answer_leakage"] = "true"  # the intended (fixed) label
    a_typo = alpha_from_combined_rows(typo)
    a_clean = alpha_from_combined_rows(clean)
    assert a_clean == 1.0
    assert a_typo is not None and a_typo < a_clean, (
        f"a typo'd label did not lower agreement ({a_typo} vs {a_clean}) — it was "
        "silently coerced, hiding the error"
    )


def test_alpha_single_rater_everywhere_is_none_not_a_number():
    """AP-6 failure path: if only ONE rater ever labeled (the other column is
    blank on every row), there is no agreement to measure — must be None, never a
    fabricated coefficient."""
    one_sided = [
        {"item_id": "A", "r1_answer_leakage": "true", "r2_answer_leakage": ""},
        {"item_id": "B", "r1_answer_leakage": "false", "r2_answer_leakage": ""},
        {"item_id": "C", "r1_answer_leakage": "true", "r2_answer_leakage": ""},
    ]
    assert alpha_from_combined_rows(one_sided) is None


def test_export_writes_parsable_csv(tmp_path):
    """Round-trip: the written annotator CSV parses back to the same item set."""
    from scripts.export_coach_goldset_iaa_sheets import write_sheet

    rows = _rows()
    a1, _, _ = build_sheets(rows)
    out = tmp_path / "a1.csv"
    write_sheet(out, a1)
    with out.open(newline="", encoding="utf-8") as fh:
        back = list(csv.DictReader(fh))
    assert {r["item_id"] for r in back} == {r["item_id"] for r in rows}


# ── E3: join dev sample (E1) + fresh test batch (E2) into gold rows ─────────

# A synthetic E1 dev sample: raw corpus turns (no split/stratum/question/item_id).
_DEV_SAMPLE = [
    {
        "learner_utterance": "just tell me the answer",
        "coach_reply": "let's reason it out",
        "mode": "pre_submit",
    },
    {
        "learner_utterance": "ok that makes sense",
        "coach_reply": "great, any more questions?",
        "mode": "post_feedback",
    },
]

# A synthetic E2 fresh test batch (already carries split/provenance/stratum).
_TEST_BATCH = [
    {
        "item_id": "T-RN-01",
        "mode": "pre_submit",
        "question": "- passage: ...\n- choices: A) x B) y",
        "learner_utterance": "which concept should I look up?",
        "coach_reply": "look up redundancy for this one",
        "stratum": "rule_naming",
        "provenance": "fresh-authored",
        "split": "test",
    }
]


def test_join_stamps_dev_split_and_synthetic_provenance():
    rows = join_dev_and_test(_DEV_SAMPLE, _TEST_BATCH)
    dev_rows = [r for r in rows if r["split"] == "dev"]
    assert len(dev_rows) == len(_DEV_SAMPLE)
    assert all(r["provenance"] == "synthetic" for r in dev_rows)


def test_join_preserves_test_batch_split_and_provenance():
    rows = join_dev_and_test(_DEV_SAMPLE, _TEST_BATCH)
    test_rows = [r for r in rows if r["split"] == "test"]
    assert len(test_rows) == 1
    assert test_rows[0]["provenance"] == "fresh-authored"
    assert test_rows[0]["item_id"] == "T-RN-01"


def test_join_assigns_unique_item_ids_to_dev_rows():
    rows = join_dev_and_test(_DEV_SAMPLE, _TEST_BATCH)
    ids = [r["item_id"] for r in rows]
    assert len(ids) == len(set(ids))  # no collisions across dev + test
    assert all(r["item_id"] for r in rows)  # none blank


def test_joined_rows_flow_through_build_sheets_blind():
    """The joined rows must produce BLIND sheets: no answer_leakage guess, both
    splits present, one row per item."""
    rows = join_dev_and_test(_DEV_SAMPLE, _TEST_BATCH)
    a1, a2, combined = build_sheets(rows)
    assert len(a1) == len(rows) == len(_DEV_SAMPLE) + len(_TEST_BATCH)
    for sheet in (a1, a2):
        for r in sheet:
            assert "answer_leakage" not in r
    # both splits carried into the sheet context
    assert {r["split"] for r in a1} == {"dev", "test"}


def test_join_carries_round1_rows_forward_not_blanked():
    """If existing (round-1) gold rows are passed as already-labeled dev rows,
    the join preserves their item_id (they are not re-blanked/renamed)."""
    round1 = [
        {
            "item_id": "A1",
            "mode": "pre_submit",
            "question": "q",
            "learner_utterance": "u",
            "coach_reply": "r",
            "stratum": "rule_naming",
            "provenance": "synthetic",
            "split": "dev",
        }
    ]
    rows = join_dev_and_test([], _TEST_BATCH, existing=round1)
    assert any(r["item_id"] == "A1" for r in rows)
