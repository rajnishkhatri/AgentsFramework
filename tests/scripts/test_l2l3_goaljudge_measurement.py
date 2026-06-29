"""Tests for the GoalJudge-vs-seed measurement (harvest + binary maps + metrics).

No live LLM. The load-bearing test is the POLARITY one: confusion_counts treats
"not-met" as the positive class, so fp must come out as "judge not-met ∧ gold met"
(the false-downgrade) — a sign flip there would silently invert the headline finding.
"""

from __future__ import annotations

import json

import pytest

from scripts.measure_l2l3_goaljudge import (
    HARNESS_BUG_PREFIXES,
    TRUNCATED_AT_SOURCE,
    _gold_met,
    _is_excluded_from_clean,
    _is_harness_bug,
)
from services.governance.goaljudge_calibration import (
    confusion_counts,
    precision_recall_fd,
)


class TestPartialMapping:
    def test_strict(self):
        assert _gold_met("correct", "strict") is True
        assert _gold_met("partial", "strict") is False
        assert _gold_met("wrong", "strict") is False

    def test_lenient(self):
        assert _gold_met("correct", "lenient") is True
        assert _gold_met("partial", "lenient") is True
        assert _gold_met("wrong", "lenient") is False

    def test_exclude_partial_drops_partial(self):
        assert _gold_met("correct", "exclude-partial") is True
        assert _gold_met("partial", "exclude-partial") is None  # dropped
        assert _gold_met("wrong", "exclude-partial") is False

    def test_unknown_mapping_raises(self):
        with pytest.raises(ValueError):
            _gold_met("correct", "nonsense")


class TestPolarity:
    """confusion_counts: both maps are item_id -> goal_met (True=met); the positive
    class is 'not-met'. Lock fp = judge not-met ∧ gold met (false downgrade)."""

    def test_false_downgrade_is_fp(self):
        # one item: judge says NOT met, gold says MET -> a false downgrade -> fp
        judge = {"x": False}
        gold = {"x": True}
        c = confusion_counts(judge, gold)
        assert (c.tp, c.fp, c.fn, c.tn) == (0, 1, 0, 0)

    def test_missed_failure_is_fn(self):
        # judge says MET, gold says NOT met -> missed failure -> fn
        c = confusion_counts({"x": True}, {"x": False})
        assert (c.tp, c.fp, c.fn, c.tn) == (0, 0, 1, 0)

    def test_true_positive_is_both_notmet(self):
        c = confusion_counts({"x": False}, {"x": False})
        assert (c.tp, c.fp, c.fn, c.tn) == (1, 0, 0, 0)

    def test_precision_recall_from_known_counts(self):
        # tp=2 fp=1 fn=1 tn=4 -> precision 2/3, recall 2/3, FD 1/5
        judge = {
            "a": False,
            "b": False,
            "c": False,
            "d": True,
            "e": True,
            "f": True,
            "g": True,
            "h": True,
        }
        gold = {
            "a": False,
            "b": False,
            "c": True,
            "d": False,
            "e": True,
            "f": True,
            "g": True,
            "h": True,
        }
        c = confusion_counts(judge, gold)
        assert (c.tp, c.fp, c.fn, c.tn) == (2, 1, 1, 4)
        prf = precision_recall_fd(c)
        assert prf.precision == pytest.approx(2 / 3)
        assert prf.recall == pytest.approx(2 / 3)
        assert prf.false_downgrade_rate == pytest.approx(1 / 5)


class TestCleanSubset:
    def test_fifteen_harness_bug_prefixes(self):
        assert len(HARNESS_BUG_PREFIXES) == 15

    def test_is_harness_bug_matches_named(self):
        assert _is_harness_bug("f623fe114eb1574cab272f28ef3dbaf1")  # access-failure
        assert _is_harness_bug("9c18000e4bef59c58a88d1b2cd9fa376")  # off-topic
        assert not _is_harness_bug("df252d5175f35826bfb632ca941cad54")  # a clean item

    def test_clean_drops_exactly_fifteen(self):
        # synthesize 53 item ids: the 15 named + 38 clean placeholders
        named = [p + "0" * (32 - len(p)) for p in HARNESS_BUG_PREFIXES]
        clean = [f"{i:032x}" for i in range(1, 39)]
        all_items = named + clean
        kept = [i for i in all_items if not _is_harness_bug(i)]
        assert len(all_items) == 53
        assert len(kept) == 38


class TestTruncatedAtSourceExclusion:
    """Growth wave: answers cut at the 500-char harvest clip before their
    load-bearing conclusion. GoalJudge correctly marks a cut-off answer not-met
    while the human read through the truncation per protocol — so these are a
    data-capture defect, NOT a judge error, and are dropped from the CLEAN gate
    exactly like the base-wave env-defect items (precedent: 70ff3369). The list
    is keyed on the truncation criterion, NOT on whether the row helps/hurts the
    gate (no outcome-driven cherry-picking).

    The original 4-arm growth wave contributed 18 truncated items; the 5th arm
    (glm-5.1, added 2026-06-28) contributed 5 more under the SAME ans_len>=498
    criterion (2 of them false-downgrades, 3 not — all 5 excluded uniformly) for
    a total of 23."""

    def test_twentythree_truncated_items(self):
        assert len(TRUNCATED_AT_SOURCE) == 23

    def test_truncation_is_separate_from_harness_bug(self):
        # The two exclusion categories must not be conflated: the harness-bug set
        # stays exactly 15 (env defects), truncation is its own audited category.
        assert len(HARNESS_BUG_PREFIXES) == 15
        assert not (set(TRUNCATED_AT_SOURCE) & HARNESS_BUG_PREFIXES)

    def test_clean_excludes_both_categories(self):
        a_truncated = next(iter(TRUNCATED_AT_SOURCE))
        a_harness = next(iter(HARNESS_BUG_PREFIXES)) + "0" * 24
        a_clean = "df252d5175f35826bfb632ca941cad54"
        assert _is_excluded_from_clean(a_truncated)
        assert _is_excluded_from_clean(a_harness)
        assert not _is_excluded_from_clean(a_clean)

    def test_harness_bug_alone_does_not_match_truncated(self):
        # _is_harness_bug stays narrow (env defects only); truncation rides the
        # broader _is_excluded_from_clean so the two stay independently auditable.
        a_truncated = next(iter(TRUNCATED_AT_SOURCE))
        assert not _is_harness_bug(a_truncated)


class TestRealArtifacts:
    """Smoke against the produced artifacts if present (skip in a clean env)."""

    def test_verdicts_and_seed_align(self):
        from scripts.measure_l2l3_goaljudge import GJ_VERDICTS, SEED

        if not (GJ_VERDICTS.exists() and SEED.exists()):
            pytest.skip("artifacts not built in this env")
        gj = json.loads(GJ_VERDICTS.read_text())
        seed = {r["item_id"] for r in json.loads(SEED.read_text())["rows"]}
        assert set(gj) == seed, "verdict/seed item sets must match exactly"
        for v in gj.values():
            assert isinstance(v["goal_met"], bool)
