"""B0/B1 tests — the fresh re-cert split builder + Mode-B shaping.

Fresh-recert spec FR-4 (balance), FR-5 (fresh text), FR-6 (item-enriched, and the
``export_coach_goldset_iaa_sheets`` Mode-B ``--test-batch`` shape). All L1: pure
authored data, no LLM, runs in ``make check``.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_coach_recert_split import build_rows, shape_test_batch

REPO_ROOT = Path(__file__).resolve().parents[2]
_39_LABELS = REPO_ROOT / "cache/open_coding/coach-phase39-tnr-fps/test_labels.jsonl"


# ── B0: authored split balance + fresh text ───────────────────────────────────


def test_recert_split_balance():
    """FR-4: leak share in [0.20,0.40], ≥20 clean, ≥10 leak."""
    rows = build_rows()
    n = len(rows)
    n_leak = sum(1 for r in rows if r["gold_leak"])
    n_clean = n - n_leak
    share = n_leak / n
    assert 0.20 <= share <= 0.40, f"leak_share {share:.3f} outside [0.20,0.40]"
    assert n_clean >= 20, f"only {n_clean} clean rows (<20)"
    assert n_leak >= 10, f"only {n_leak} leak rows (<10)"


def test_recert_ids_unique():
    """Every authored row has a unique item_id (no accidental dup)."""
    rows = build_rows()
    ids = [r["case_id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_recert_utterances_fresh():
    """FR-5: no authored utterance reuses a 3.9 utterance (verbatim, case-insensitive)."""
    if not _39_LABELS.exists():  # the 3.9 label dump is a local cache artifact
        import pytest

        pytest.skip("3.9 label dump not present (local cache artifact)")
    old = {
        json.loads(line)["learner_utterance"].strip().lower()
        for line in _39_LABELS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    new = [r["learner_utterance"].strip().lower() for r in build_rows()]
    overlap = sorted(set(new) & old)
    assert overlap == [], (
        f"{len(overlap)} authored utterances reuse 3.9 text: {overlap[:3]}"
    )


# ── B1: Mode-B shaping (the --test-batch contract) ────────────────────────────


def test_shape_test_batch_is_mode_b_ready():
    """FR-6: shaping renders each row into the export_coach_goldset_iaa_sheets
    Mode-B ``--test-batch`` shape — an ``item_id`` (not a bare question_id as the
    id), ``split=test``, ``provenance=fresh-authored``, and a non-empty rendered
    ``question`` block resolved from the item bank."""
    shaped = shape_test_batch(build_rows())
    assert shaped, "no rows shaped"
    for r in shaped:
        assert r["item_id"].startswith(("R-CLEAN-", "R-LEAK-")), r["item_id"]
        assert r["split"] == "test"
        assert r["provenance"] == "fresh-authored"
        # the rendered item block, not the bare question_id
        assert r["question"].strip(), f"{r['item_id']} has no rendered question"
        assert not r["question"].strip().startswith("q-"), "looks like a bare id"
        assert r["mode"] in {"pre_submit", "post_feedback"}
        assert "stratum" in r


def test_shape_test_batch_pre_submit_strips_key():
    """FR-6: a pre_submit row's rendered question must NOT reveal the answer key
    (the judge decides leakage blind); a post_feedback row includes it."""
    shaped = shape_test_batch(build_rows())
    pre = next(r for r in shaped if r["mode"] == "pre_submit")
    post = next(r for r in shaped if r["mode"] == "post_feedback")
    assert "correct answer" not in pre["question"].lower()
    assert "correct answer" in post["question"].lower()


# ── B2: blind double-label sheet contract ─────────────────────────────────────


def test_iaa_sheets_are_blind_no_author_label():
    """FR-3 (blind labeling): exporting the shaped rows through the Mode-B sheet
    builder must NOT surface the author's ``author_gold_leak`` (or any gold guess)
    into the annotator/combined sheets — the human labels blind. The only leakage
    columns are the EMPTY rater fields the annotators fill in."""
    from scripts.export_coach_goldset_iaa_sheets import build_sheets

    shaped = shape_test_batch(build_rows())
    a1, a2, combined = build_sheets(shaped)
    assert a1 and a2 and combined
    for sheet in (a1, a2, combined):
        cols = set(sheet[0].keys())
        assert "author_gold_leak" not in cols
        assert "gold_leak" not in cols
        # rater columns exist but are EMPTY (nothing pre-filled)
        rater_cols = [c for c in cols if c.endswith("_answer_leakage")]
        assert rater_cols, "no rater answer_leakage column to fill"
        for row in sheet:
            for rc in rater_cols:
                assert row[rc] == "", f"{rc} pre-filled — not blind"
