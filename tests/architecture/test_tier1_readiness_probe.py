"""Tier-1 taxonomy-readiness probe gates (FR-1…FR-9) + verdict-drift lock.

Companion to ``scripts/tier1_taxonomy_readiness.py``. Mirrors
``test_syllabus_coverage_ratchet.py``: import pure helpers, assert FRs,
lock committed verdict == fresh run.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.tier1_taxonomy_readiness import (
    DEFAULT_OUT,
    build_result,
    DEFAULT_MISSES_PER_LEARNER,
    DEFAULT_N_LEARNERS,
    DEFAULT_SEED,
    MIN_CLUSTER_SIZE_FOR_GATE,
    MIN_FIRE_RATE,
    MIN_MEANINGFUL_CLUSTERS,
    fires_for_misses,
    integrity_warnings,
    load_bank,
    load_syllabus,
    meaningful_clusters,
    simulate_fire_rate,
    tagged_rows,
    untagged_ids,
    verdict,
)

_REPO = Path(__file__).resolve().parent.parent.parent
_CORPUS = _REPO / "docs" / "plan" / "coach-item-bank-live.promoted.json"
_SYLLABUS = _REPO / "docs" / "plan" / "act-english-syllabus.seed.json"


class TestFR1UntaggedNeverCounted:
    """FR-1 — null/empty misconception excluded from every count."""

    def test_untagged_items_never_counted(self):
        bank = [
            {
                "id": "a",
                "misconception": "real tag",
                "skill_id": "s-sent",
                "standard_id": 15,
            },
            {"id": "b", "misconception": None, "skill_id": "s-sent", "standard_id": 15},
            {"id": "c", "misconception": "", "skill_id": "s-sent", "standard_id": 15},
            {
                "id": "d",
                "misconception": "   ",
                "skill_id": "s-sent",
                "standard_id": 15,
            },
        ]
        tagged = tagged_rows(bank)
        assert [r["id"] for r in tagged] == ["a"]
        assert set(untagged_ids(bank)) == {"b", "c", "d"}


class TestFR5PerSkillCoverage:
    """FR-5 — per-skill totals reconcile on today's bank."""

    def test_per_skill_coverage_counts(self):
        bank = load_bank(_CORPUS)
        syllabus = load_syllabus(_SYLLABUS)
        assert len(bank) == 171
        tagged = tagged_rows(bank)
        assert len(tagged) == 47
        assert len(untagged_ids(bank)) == 171 - 47
        # Syllabus per-skill standard counts (FR-3 substrate).
        assert {k: len(v) for k, v in syllabus.items()} == {
            "s-gram": 14,
            "s-punc": 5,
            "s-sent": 6,
            "s-style": 4,
            "s-rhet": 2,
            "s-org": 1,
        }


class TestFR2NoManufacturedThemes:
    """FR-2 — free-text word overlap NEVER forms a cluster; key is standard_id."""

    def test_free_text_overlap_never_clusters(self):
        syllabus = {"s-gram": {10, 11, 12}}
        tagged = [
            {
                "id": "a",
                "skill_id": "s-gram",
                "standard_id": 10,
                "misconception": "where vs were confusion A",
            },
            {
                "id": "b",
                "skill_id": "s-gram",
                "standard_id": 11,
                "misconception": "where vs were confusion B",
            },
            {
                "id": "c",
                "skill_id": "s-gram",
                "standard_id": 12,
                "misconception": "where vs were confusion C",
            },
        ]
        clusters = meaningful_clusters(tagged, syllabus)
        # Shared word "where" must NOT unite them — different standard_ids.
        assert clusters["clusters"] == {}
        assert all(isinstance(k[1], int) for k in clusters["clusters"])
        assert clusters["label"] == "candidate"


class TestFR3SingleStandardExcluded:
    """FR-3 — single-standard skills marked not-meaningful, excluded from gate."""

    def test_single_standard_skill_marked_not_meaningful(self):
        syllabus = {"s-org": {1}, "s-sent": {14, 15}}
        tagged = [
            {"id": "o1", "skill_id": "s-org", "standard_id": 1, "misconception": "a"},
            {"id": "o2", "skill_id": "s-org", "standard_id": 1, "misconception": "b"},
            {"id": "o3", "skill_id": "s-org", "standard_id": 1, "misconception": "c"},
            {"id": "o4", "skill_id": "s-org", "standard_id": 1, "misconception": "d"},
            {"id": "o5", "skill_id": "s-org", "standard_id": 1, "misconception": "e"},
            {"id": "s1", "skill_id": "s-sent", "standard_id": 15, "misconception": "x"},
            {"id": "s2", "skill_id": "s-sent", "standard_id": 15, "misconception": "y"},
        ]
        result = meaningful_clusters(tagged, syllabus)
        assert ("s-org", 1) not in result["clusters"]
        assert ("s-org", 1) in result["not_meaningful"]
        assert result["not_meaningful"][("s-org", 1)] == 5
        assert result["clusters"][("s-sent", 15)] == 2


class TestFR4CandidateNotTheme:
    """FR-4 — every surfaced cluster is labelled candidate, never confirmed theme."""

    def test_clusters_labelled_candidate_not_theme(self):
        syllabus = {"s-sent": {14, 15}}
        tagged = [
            {"id": "a", "skill_id": "s-sent", "standard_id": 15, "misconception": "x"},
            {"id": "b", "skill_id": "s-sent", "standard_id": 15, "misconception": "y"},
        ]
        result = meaningful_clusters(tagged, syllabus)
        assert result["label"] == "candidate"
        assert "theme" not in result["label"]
        warnings = integrity_warnings(
            [
                {
                    "id": "bad",
                    "skill_id": "s-sent",
                    "standard_id": 99,
                    "misconception": "orphan",
                }
            ],
            syllabus,
        )
        assert warnings
        assert "99" in warnings[0]


class TestFR6FireRate:
    """FR-6 — ≥2 misses in one meaningful cluster fires; across clusters does not."""

    def test_fire_rate_counts_two_in_one_cluster(self):
        syllabus = {"s-sent": {14, 15}, "s-style": {5, 6}}
        cluster_a = [
            {"id": "a1", "skill_id": "s-sent", "standard_id": 15, "misconception": "x"},
            {"id": "a2", "skill_id": "s-sent", "standard_id": 15, "misconception": "y"},
        ]
        across = [
            {"id": "b1", "skill_id": "s-sent", "standard_id": 14, "misconception": "p"},
            {"id": "b2", "skill_id": "s-style", "standard_id": 5, "misconception": "q"},
        ]
        # Meaningful keys that exist in the bank (cluster size ≥2).
        meaningful_keys = {("s-sent", 15)}
        assert fires_for_misses(cluster_a, meaningful_keys, due_skills=None) is True
        assert fires_for_misses(across, meaningful_keys, due_skills=None) is False

        # Full sim: dense single cluster → positive overall under all_due.
        tagged = cluster_a + [
            {"id": "a3", "skill_id": "s-sent", "standard_id": 15, "misconception": "z"},
            {"id": "c1", "skill_id": "s-style", "standard_id": 5, "misconception": "r"},
            {"id": "c2", "skill_id": "s-style", "standard_id": 6, "misconception": "s"},
        ]
        result = simulate_fire_rate(
            tagged,
            syllabus,
            n_learners=200,
            misses_per_learner=2,
            due_model="all_due",
            seed=7,
        )
        assert result["due_model"] == "all_due"
        assert result["structural_zero"] is False
        assert result["overall"] is not None
        assert result["overall"] > 0.0


class TestFR7DueModelExplicit:
    """FR-7 — due_model is an explicit param; changing it changes the number."""

    def test_due_model_is_explicit_param(self):
        syllabus = {"s-sent": {14, 15}}
        tagged = [
            {"id": "a1", "skill_id": "s-sent", "standard_id": 15, "misconception": "x"},
            {"id": "a2", "skill_id": "s-sent", "standard_id": 15, "misconception": "y"},
            {"id": "a3", "skill_id": "s-sent", "standard_id": 15, "misconception": "z"},
        ]
        all_due = simulate_fire_rate(
            tagged,
            syllabus,
            n_learners=100,
            misses_per_learner=2,
            due_model="all_due",
            seed=42,
        )
        none_due = simulate_fire_rate(
            tagged,
            syllabus,
            n_learners=100,
            misses_per_learner=2,
            due_model="none_due",
            seed=42,
        )
        assert all_due["due_model"] == "all_due"
        assert none_due["due_model"] == "none_due"
        assert all_due["overall"] != none_due["overall"]
        assert none_due["overall"] == 0.0
        # Deterministic under fixed seed.
        again = simulate_fire_rate(
            tagged,
            syllabus,
            n_learners=100,
            misses_per_learner=2,
            due_model="all_due",
            seed=42,
        )
        assert again["overall"] == all_due["overall"]


class TestFR8Verdict:
    """FR-8 — build iff BOTH thresholds clear; else defer + reason."""

    def test_verdict_build_iff_thresholds_clear(self):
        # Both clear → build.
        clusters = {("s-sent", 15): 3, ("s-style", 5): 3}
        fire = {"overall": 0.10, "due_model": "all_due", "structural_zero": False}
        built = verdict(clusters, fire)
        assert built["verdict"] == "build"
        assert built["thresholds"] == {
            "min_meaningful_clusters": MIN_MEANINGFUL_CLUSTERS,
            "min_cluster_size": MIN_CLUSTER_SIZE_FOR_GATE,
            "min_fire_rate": MIN_FIRE_RATE,
        }
        assert built["reasons"] == []

        # Cluster gate fails → defer.
        thin = verdict({("s-sent", 15): 2}, fire)
        assert thin["verdict"] == "defer"
        assert any("cluster" in r.lower() for r in thin["reasons"])

        # Fire-rate gate fails → defer.
        cold = verdict(clusters, {**fire, "overall": 0.01})
        assert cold["verdict"] == "defer"
        assert any("fire" in r.lower() for r in cold["reasons"])

        # Both fail → defer with both reasons.
        both = verdict({("s-sent", 15): 2}, {**fire, "overall": 0.01})
        assert both["verdict"] == "defer"
        assert len(both["reasons"]) >= 2

    def test_verdict_defer_or_build_on_todays_bank(self):
        bank = load_bank(_CORPUS)
        syllabus = load_syllabus(_SYLLABUS)
        tagged = tagged_rows(bank)
        cluster_info = meaningful_clusters(tagged, syllabus)
        fire = simulate_fire_rate(
            tagged,
            syllabus,
            n_learners=DEFAULT_N_LEARNERS,
            misses_per_learner=DEFAULT_MISSES_PER_LEARNER,
            due_model="all_due",
            seed=DEFAULT_SEED,
        )
        result = verdict(cluster_info["clusters"], fire)
        # Today's bank: 4 clusters of ≥3 (gate passes); misses=2 density →
        # fire-rate below 5% → defer. Lock the measured reality.
        assert result["verdict"] == "defer"
        assert result["measured"]["n_clusters_ge_3"] >= 1
        assert result["measured"]["fire_rate"] < MIN_FIRE_RATE
        assert any("fire" in r.lower() for r in result["reasons"])


class TestFR5RenderReport:
    """FR-5 surface — coverage table + candidate list + untagged foot."""

    def test_render_report_includes_coverage_and_candidates(self):
        bank = load_bank(_CORPUS)
        syllabus = load_syllabus(_SYLLABUS)
        result = build_result(bank, syllabus)
        report = result["report"]
        assert "s-sent" in report
        assert "candidate" in report
        assert "not-meaningful" in report  # s-org FR-3
        assert "UNTAGGED" in report
        assert "due_model=" in report  # FR-7 stated
        assert "VERDICT:" in report


class TestFR9ReadOnlyDeterministic:
    """FR-9 — build_result is pure; byte-identical on repeat; only --out writes."""

    def test_probe_is_read_only_deterministic(self, tmp_path):
        bank_bytes_before = _CORPUS.read_bytes()
        bank = load_bank(_CORPUS)
        syllabus = load_syllabus(_SYLLABUS)
        a = build_result(bank, syllabus)
        b = build_result(bank, syllabus)
        assert a["report"] == b["report"]
        assert json.dumps(a["verdict"], sort_keys=True) == json.dumps(
            b["verdict"], sort_keys=True
        )
        out = tmp_path / "verdict.json"
        out.write_text(json.dumps(a["verdict"], indent=2) + chr(10))
        assert out.exists()
        assert _CORPUS.read_bytes() == bank_bytes_before


class TestVerdictDriftLock:
    """Committed verdict == fresh run (mirrors coverage-floor ratchet)."""

    def test_committed_verdict_matches_fresh_run(self):
        assert DEFAULT_OUT.exists(), "committed verdict JSON missing"
        committed = json.loads(DEFAULT_OUT.read_text(encoding="utf-8"))
        fresh = build_result(load_bank(_CORPUS), load_syllabus(_SYLLABUS))["verdict"]
        assert committed == fresh
