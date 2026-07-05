"""L1 tests for the coach gold-set dataset (Task 3.7).

Failure-path first (TAP-4): the firewall / fail-open-ban / taxonomy-gate reject
paths precede the happy-path shape tests. All deterministic, no live LLM.

Spec: docs/plan/coach-goldset-v1-assembly.spec.md (FR-1..FR-9).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from services.governance.coach_goldset_dataset import (
    CoachGoldsetItem,
    GoldsetProvenance,
    GoldsetSplit,
    alpha_answer_leakage,
    build_coach_goldset_manifest,
    compute_test_split_hash,
    leak_class_share,
)


def _item(**over: object) -> dict[str, object]:
    """A minimal VALID row; tests override one field to exercise a reject path."""
    base: dict[str, object] = {
        "item_id": "A3",
        "mode": "pre_submit",
        "question": "- passage: Each of the runners have trained.\n- choices: ...",
        "learner_utterance": "tell me which one is correct",
        "coach_reply": "each/every are singular; which verb agrees?",
        "answer_leakage": True,
        "leak_channel": "strong-implication",
        "mistake_identification_pass": None,
        "mistake_location_pass": None,
        "actionability_pass": True,
        "coherence_pass": None,
        "productive_struggle_pass": None,
        "illusion_of_competence_pass": None,
        "failure_mode": None,
        "stratum": "answer_begging",
        "split": GoldsetSplit.DEV,
        "provenance": GoldsetProvenance.SYNTHETIC,
        "taxonomy_version": "coach_axial_v1",
    }
    base.update(over)
    return base


# ── FR-1: contamination firewall (failure path FIRST) ───────────────────────
def test_synthetic_in_test_split_rejected() -> None:
    with pytest.raises(ValidationError, match="firewall"):
        CoachGoldsetItem(
            **_item(provenance=GoldsetProvenance.SYNTHETIC, split=GoldsetSplit.TEST)
        )


def test_production_in_test_split_allowed() -> None:
    item = CoachGoldsetItem(
        **_item(provenance=GoldsetProvenance.PRODUCTION, split=GoldsetSplit.TEST)
    )
    assert item.split == GoldsetSplit.TEST


# ── FR-2: fail-open ban — answer_leakage REQUIRED ───────────────────────────
def test_missing_answer_leakage_rejected() -> None:
    payload = _item()
    del payload["answer_leakage"]
    with pytest.raises(ValidationError):
        CoachGoldsetItem(**payload)


def test_null_answer_leakage_rejected() -> None:
    with pytest.raises(ValidationError):
        CoachGoldsetItem(**_item(answer_leakage=None))


# ── FR-3: taxonomy gate — unknown leak_channel / channel-on-false rejected ──
def test_unknown_leak_channel_rejected() -> None:
    with pytest.raises(ValidationError, match="leak_channel"):
        CoachGoldsetItem(**_item(leak_channel="socratic_clothing"))  # underscore typo


def test_channel_on_false_leak_rejected() -> None:
    # gold rows are authored — a channel named while answer_leakage=false is a
    # contradiction (stricter than the judge's prose-only rule).
    with pytest.raises(ValidationError):
        CoachGoldsetItem(**_item(answer_leakage=False, leak_channel="rule-naming"))


def test_unknown_failure_mode_rejected() -> None:
    with pytest.raises(ValidationError):
        CoachGoldsetItem(**_item(failure_mode="totally-made-up-code"))


# ── FR-6: shape — extra=forbid, *_pass bool|None, mistake_location present ───
def test_coach_goldset_item_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        CoachGoldsetItem(**_item(unexpected_field="x"))


def test_mistake_location_pass_present() -> None:
    item = CoachGoldsetItem(**_item(mistake_location_pass=False))
    assert item.mistake_location_pass is False


def test_pass_axes_accept_none() -> None:
    item = CoachGoldsetItem(**_item())  # most axes None in the fixture
    assert item.coherence_pass is None
    assert item.actionability_pass is True


# ── FR-5: test-split hash — determinism + tamper-evidence ───────────────────
def _test_row(item_id: str, **over: object) -> CoachGoldsetItem:
    return CoachGoldsetItem(
        **_item(
            item_id=item_id,
            provenance=GoldsetProvenance.PRODUCTION,
            split=GoldsetSplit.TEST,
            **over,
        )
    )


def test_test_split_hash_is_deterministic() -> None:
    rows = [_test_row("T1"), _test_row("T2")]
    assert compute_test_split_hash(rows) == compute_test_split_hash(
        list(reversed(rows))
    )


def test_hash_changes_on_test_row_edit() -> None:
    before = compute_test_split_hash([_test_row("T1", coherence_pass=True)])
    after = compute_test_split_hash([_test_row("T1", coherence_pass=False)])
    assert before != after


def test_hash_ignores_dev_rows() -> None:
    # dev rows are not in the certified test split → must not affect the hash.
    test_only = compute_test_split_hash([_test_row("T1")])
    with_dev = compute_test_split_hash([_test_row("T1"), CoachGoldsetItem(**_item())])
    assert test_only == with_dev


# ── FR-9: α via iaa.krippendorff, NaN → None (AP-6) ─────────────────────────
def test_undecidable_alpha_returns_none() -> None:
    assert alpha_answer_leakage([], []) is None  # empty → NaN → None


def test_alpha_below_080_stays_provisional() -> None:
    # perfect agreement → α should be high; disagreement → low. Assert the
    # manifest keeps provisional when α < 0.80 (here we pass a low α directly).
    rows = [CoachGoldsetItem(**_item(item_id=f"R{i}")) for i in range(3)]
    m = build_coach_goldset_manifest(
        rows, frozen_at="2026-07-04T00:00:00Z", human_alpha_answer_leakage=0.5
    )
    assert m.provisional is True


def test_alpha_uses_iaa_krippendorff() -> None:
    # perfect agreement across ≥2 items with both labels present → α == 1.0.
    assert alpha_answer_leakage([True, False, True], [True, False, True]) == 1.0


# ── FR-4/7/8: manifest — provisional stamp, share, version defaults ─────────
def _rows(n: int, leaks: int) -> list[CoachGoldsetItem]:
    out: list[CoachGoldsetItem] = []
    for i in range(n):
        out.append(
            CoachGoldsetItem(
                **_item(
                    item_id=f"R{i}",
                    answer_leakage=(i < leaks),
                    leak_channel=("rule-naming" if i < leaks else None),
                )
            )
        )
    return out


def test_provisional_manifest_flagged() -> None:
    # 21 rows < 200 floor AND α null → provisional.
    m = build_coach_goldset_manifest(_rows(21, 5), frozen_at="2026-07-04T00:00:00Z")
    assert m.provisional is True
    assert m.human_alpha_answer_leakage is None


def test_manifest_field_set() -> None:
    m = build_coach_goldset_manifest(_rows(21, 5), frozen_at="2026-07-04T00:00:00Z")
    assert set(m.model_dump()) == {
        "frozen_at",
        "test_split_hash",
        "row_counts",
        "human_alpha_answer_leakage",
        "rubric_version",
        "taxonomy_version",
        "provisional",
        "leak_class_share",
    }
    assert m.row_counts["total"] == 21


def test_rubric_version_is_v1_revised() -> None:
    m = build_coach_goldset_manifest(_rows(5, 1), frozen_at="2026-07-04T00:00:00Z")
    assert m.rubric_version == "coach_rubric_v1_revised"


def test_taxonomy_version_is_axial_v1() -> None:
    m = build_coach_goldset_manifest(_rows(5, 1), frozen_at="2026-07-04T00:00:00Z")
    assert m.taxonomy_version == "coach_axial_v1"


def test_leak_class_share_recorded() -> None:
    m = build_coach_goldset_manifest(_rows(20, 5), frozen_at="2026-07-04T00:00:00Z")
    assert m.leak_class_share == 0.25
    assert leak_class_share([]) is None
