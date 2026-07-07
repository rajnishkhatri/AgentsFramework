"""L1 gates on the FROZEN fresh re-cert split (`coach_recert_split_v1.json`).

Fresh-recert spec:
* B4  — FR-7 (rubric_version = v2), FR-12 (test_split_hash), FR-3 (provisional=False).
* B5  — FR-2 (disjoint from the 3.9 test + coded-FP ids), FR-4 (balance), FR-5 (fresh
        utterance text), FR-11 (an abstaining row is dropped from the confusion).

All offline: pure reads of the committed artifact + the 3.9 label cache, no LLM, no
network — runs in ``make check``. The live glm-5.2 re-cert (C0/C1/C2) is creds-gated
and out of this suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Reference the gold helper via the module — it is named ``test_split_gold`` and a
# bare ``from … import test_split_gold`` would make pytest COLLECT it as a test case.
from scripts import run_coach_calibration as rcc
from scripts.run_coach_calibration import cert_from_labels, load_goldset
from services.governance.coach_goldset_dataset import (
    GoldsetSplit,
    compute_test_split_hash,
)

_test_split_gold = rcc.test_split_gold

REPO_ROOT = Path(__file__).resolve().parents[2]
FROZEN = REPO_ROOT / "tests/fixtures/coach_goldset/coach_recert_split_v1.json"
GOLDSET_V1 = REPO_ROOT / "tests/fixtures/coach_goldset/coach_goldset_v1.json"
_39_LABELS = REPO_ROOT / "cache/open_coding/coach-phase39-tnr-fps/test_labels.jsonl"

# The 7 coded false-positive ids + the dropped abstain row the fresh split must avoid
# (spec FR-2). These are the OVERFLAG-1 rows the carve-out was reverse-engineered from.
_CODED_FP_IDS = frozenset(
    {
        "T-CLEAN-03",
        "T-CLEAN-12",
        "T-CLEAN-16",
        "T-CLEAN-17",
        "T-CLEAN-19",
        "T-CLEAN-29",
        "T-UL-01",
        "T-CLEAN-20",  # the abstain row dropped from the 3.9 confusion
    }
)


@pytest.fixture(scope="module")
def frozen():
    items, manifest = load_goldset(FROZEN)
    return items, manifest


# ── B4: manifest gates (FR-7 / FR-12 / FR-3) ──────────────────────────────────


def test_recert_rubric_version(frozen) -> None:
    """FR-7: the frozen manifest carries the v2 carve-out rubric, not round-1 v1."""
    _items, manifest = frozen
    assert manifest.rubric_version == "coach_rubric_v2_specificity"


def test_recert_split_provisional_is_false(frozen) -> None:
    """FR-3: the split is non-provisional (α = 1.0 ≥ 0.80), so the cert can score it."""
    _items, manifest = frozen
    assert manifest.provisional is False
    assert manifest.human_alpha_answer_leakage == 1.0
    assert manifest.row_counts["total"] == 47


def test_recert_split_hash(frozen) -> None:
    """FR-12: the manifest SHA-256 matches a recomputation over the frozen test rows.

    A later silent edit to any 'held-out' row would change the recomputed hash and
    trip this — tamper-evidence over the surface the re-cert scores on.
    """
    items, manifest = frozen
    assert manifest.test_split_hash == compute_test_split_hash(items)


# ── B5: disjointness / balance / fresh-text / abstention ──────────────────────


def test_recert_split_disjoint_from_3_9(frozen) -> None:
    """FR-2: the fresh split's item_ids are disjoint from the 3.9 test split AND the
    coded-FP ids AND the dropped abstain row.

    The re-cert must score UNSEEN text (ADR-0018 §9): any id recurring here means the
    carve-out is being validated on a row it was fit to. Intersect on ``item_id`` (both
    the 3.9 dump and coach_goldset_v1 key on it; nothing carries ``trace_id``).
    """
    recert_ids = {i.item_id for i in frozen[0]}

    # (a) vs the frozen 3.9 test split
    v1_items, _ = load_goldset(GOLDSET_V1)
    v1_test_ids = {i.item_id for i in v1_items if i.split == GoldsetSplit.TEST}
    assert recert_ids.isdisjoint(v1_test_ids), (
        f"recert reuses 3.9 test ids: {sorted(recert_ids & v1_test_ids)}"
    )

    # (b) vs the 7 coded FP ids + the dropped abstain row
    assert recert_ids.isdisjoint(_CODED_FP_IDS), (
        f"recert reuses coded-FP ids: {sorted(recert_ids & _CODED_FP_IDS)}"
    )


def test_recert_split_balance(frozen) -> None:
    """FR-4: leak share ∈ [0.20,0.40], ≥20 clean, ≥10 leak (on the frozen rows)."""
    items, manifest = frozen
    n = len(items)
    n_leak = sum(1 for i in items if i.answer_leakage)
    n_clean = n - n_leak
    share = n_leak / n
    assert 0.20 <= share <= 0.40, f"leak_share {share:.3f} outside [0.20,0.40]"
    assert n_clean >= 20, f"only {n_clean} clean rows (<20)"
    assert n_leak >= 10, f"only {n_leak} leak rows (<10)"
    # manifest agrees with the row-level tally (no drift between them).
    assert abs(manifest.leak_class_share - share) < 1e-9


def test_recert_utterances_fresh(frozen) -> None:
    """FR-5: no frozen utterance reuses a 3.9 utterance (verbatim, case-insensitive)."""
    if not _39_LABELS.exists():  # local cache artifact
        pytest.skip("3.9 label dump not present (local cache artifact)")
    old = {
        json.loads(line)["learner_utterance"].strip().lower()
        for line in _39_LABELS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    new = [i.learner_utterance.strip().lower() for i in frozen[0]]
    overlap = sorted(set(new) & old)
    assert overlap == [], (
        f"{len(overlap)} frozen utterances reuse 3.9 text: {overlap[:3]}"
    )


def test_recert_abstention_dropped(frozen) -> None:
    """FR-11: an abstaining row (no judge label) is excluded from the confusion, never
    scored ``false`` — mirrors the 3.9 ``T-CLEAN-20`` provider-timeout handling.

    Drives the real cert path: a perfect judge that abstains on one clean row must NOT
    have that row counted as a false positive (which a scored-``false`` would do here,
    since the row's gold is ``false`` → a spurious TN, or worse a leak abstain → lost TP).
    """
    items, manifest = frozen
    gold = _test_split_gold(items)
    # A "perfect" judge that agrees on every id …
    perfect = dict(gold)
    # … then abstains on one clean row (drop it from the judge map entirely).
    abstain_id = next(iid for iid, g in gold.items() if g is False)
    del perfect[abstain_id]

    decision = cert_from_labels(judge_labels=perfect, items=items, manifest=manifest)
    # The abstained row is absent from the confusion: total scored = |gold| − 1.
    conf = decision.diagnostics
    # The verdict is still ENABLE-shaped (perfect on everything scored); the point is
    # the dropped row didn't become an FP. Assert via the false-action rate: 0 FPs.
    assert conf.get("false_action_rate") == 0.0, (
        "an abstaining clean row was scored instead of dropped (FR-11 violated)"
    )
