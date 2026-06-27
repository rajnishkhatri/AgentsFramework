"""Tests for the L2/L3 blind-adjudication scripts: seed, corpus filter, keys,
harvest, blind-set builder, and the IAA-alpha wiring.

No live LLM. Failure paths first (FD6). The blinding-leak assertion and the
sealed-key round-trip are the load-bearing guardrails of the gold-set process.
"""

from __future__ import annotations

import json

import pytest

from scripts.build_l2l3_answer_keys import build_keys
from scripts.build_l2l3_blind_set import build_blind_set, leak_scan
from scripts.build_l2l3_corpus import filter_l2l3
from scripts.harvest_l2l3_answers import final_answers_for_cases, harvest
from scripts.seed_model_ab_l2l3_workspace import (
    GROUND_TRUTH_BY_CASE,
    seed_l2l3_workspace,
)

L2L3_CASES = [
    "GEN-L2-multi-file-reconcile-07",
    "GEN-L2-cross-ref-lookup-08",
    "GEN-L2-pipeline-transform-09",
    "GEN-L2-multi-source-synthesis-10",
    "GEN-L2-verify-and-fix-11",
    "GEN-L2-dependency-resolve-12",
    "GEN-L3-constraint-solve-13",
    "GEN-L3-multi-hop-synthesis-14",
    "GEN-L3-iterative-refine-15",
]


class TestSeed:
    def test_seeds_every_referenced_dir_and_file(self, tmp_path):
        ws = seed_l2l3_workspace(tmp_path)
        for rel in (
            "invoices/inv-1.txt",
            "invoices/inv-5.txt",
            "orders.csv",
            "customers.csv",
            "events.log",
            "reports/q1.txt",
            "config.json",
            "deps.txt",
            "schedule/p1.txt",
            "papers/paper-3.txt",
            "budget.csv",
        ):
            assert (ws / rel).exists(), f"missing fixture {rel}"

    def test_tolerates_stray_file_where_dir_must_go(self, tmp_path):
        # A contaminated prior run can leave a FILE at invoices/; seeding must
        # still succeed (the _fresh_dir guard).
        (tmp_path / "invoices").write_text("this is a stray file\n")
        ws = seed_l2l3_workspace(tmp_path)
        assert (ws / "invoices").is_dir()
        assert (ws / "invoices" / "inv-1.txt").exists()

    def test_paid_subtotal_matches_ground_truth(self, tmp_path):
        ws = seed_l2l3_workspace(tmp_path)
        paid = 0
        for n in range(1, 6):
            body = (ws / "invoices" / f"inv-{n}.txt").read_text()
            if "status: paid" in body:
                amt = int(body.split("amount:")[1].split("\n")[0])
                paid += amt
        assert paid == 475
        facts = GROUND_TRUTH_BY_CASE["GEN-L2-multi-file-reconcile-07"].facts
        assert any("475" in f for f in facts)

    def test_region_counts_match_ground_truth(self, tmp_path):
        ws = seed_l2l3_workspace(tmp_path)
        cust = dict(
            line.split(",")
            for line in (ws / "customers.csv").read_text().splitlines()[1:]
        )
        from collections import Counter

        counts = Counter(
            cust[line.split(",")[1]]
            for line in (ws / "orders.csv").read_text().splitlines()[1:]
        )
        assert counts == {"north": 4, "south": 2, "west": 1}

    def test_idempotent(self, tmp_path):
        seed_l2l3_workspace(tmp_path)
        first = (tmp_path / "deps.txt").read_text()
        seed_l2l3_workspace(tmp_path)
        assert (tmp_path / "deps.txt").read_text() == first


class TestCorpusFilter:
    def test_filters_to_nine_l2l3_rows(self, tmp_path):
        # build a tiny mixed source
        src = tmp_path / "ui.jsonl"
        rows = [
            {"case": "GEN-L1-x", "difficulty": "L1", "prompt": "p"},
            {"case": "GEN-L2-y", "difficulty": "L2", "prompt": "p"},
            {"case": "GEN-L3-z", "difficulty": "L3", "prompt": "p"},
        ]
        src.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        out = filter_l2l3(src)
        assert [r["difficulty"] for r in out] == ["L2", "L3"]

    def test_preserves_all_fields(self, tmp_path):
        src = tmp_path / "ui.jsonl"
        row = {
            "case": "GEN-L2-y",
            "difficulty": "L2",
            "prompt": "p",
            "phase": "answer",
            "trace_id": "abc",
            "want_answer": "w",
        }
        src.write_text(json.dumps(row) + "\n")
        out = filter_l2l3(src)
        assert out == [row]

    def test_real_corpus_has_nine(self):
        # The actual converted corpus (if present) yields exactly 9 L2/L3 rows.
        from scripts.build_l2l3_corpus import DEFAULT_SOURCE

        if not DEFAULT_SOURCE.exists():
            pytest.skip("ui_batch.jsonl not built in this env")
        assert len(filter_l2l3(DEFAULT_SOURCE)) == 9


class TestAnswerKeys:
    def test_every_case_has_facts(self):
        keys = build_keys()
        assert set(keys) == set(L2L3_CASES)
        for case, k in keys.items():
            assert k["must_have_facts"], f"{case} has no facts"


class TestHarvest:
    def test_final_answers_last_call_wins(self, tmp_path):
        import uuid

        case = "GEN-L2-cross-ref-lookup-08"
        tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
        log = tmp_path / "evals.log"
        log.write_text(
            "\n".join(
                [
                    json.dumps(
                        {"target": "call_llm", "task_id": tid, "ai_response": "first"}
                    ),
                    json.dumps(
                        {"target": "call_llm", "task_id": tid, "ai_response": "FINAL"}
                    ),
                    json.dumps(
                        {"target": "goal_judge", "task_id": tid, "ai_response": {}}
                    ),
                ]
            )
            + "\n"
        )
        out = final_answers_for_cases(log, [case])
        assert out[case] == "FINAL"

    def test_harvest_surfaces_missing_cell(self, tmp_path):
        # An arm whose evals.log is missing -> all 9 cases reported missing.
        sources = {"phantom-arm": ("nope_run", "candidate")}
        raw, missing = harvest(sources, cases=L2L3_CASES, model_ab=tmp_path)
        assert len(missing) == 9
        assert all(arm == "phantom-arm" for arm, _ in missing)


class TestBlindSet:
    def _fixture(self, tmp_path):
        raw = tmp_path / "raw.json"
        raw.write_text(
            json.dumps(
                {
                    "claude-haiku-4-5": {
                        "GEN-L2-cross-ref-lookup-08": "north: 4, south: 2, west: 1"
                    },
                    "gpt-4o-mini": {
                        "GEN-L2-cross-ref-lookup-08": "I could not find the file"
                    },
                    "deepseek-v4-pro": {
                        "GEN-L2-cross-ref-lookup-08": ""
                    },  # empty -> skipped
                }
            )
        )
        batch = tmp_path / "batch.jsonl"
        batch.write_text(
            json.dumps(
                {
                    "case": "GEN-L2-cross-ref-lookup-08",
                    "prompt": "count orders per region",
                }
            )
            + "\n"
        )
        keys = tmp_path / "keys.json"
        keys.write_text(
            json.dumps(
                {"GEN-L2-cross-ref-lookup-08": {"must_have_facts": ["north: 4"]}}
            )
        )
        return raw, batch, keys

    def test_empty_answer_skipped(self, tmp_path):
        raw, batch, keys = self._fixture(tmp_path)
        items, sealed, skipped = build_blind_set(raw, batch, keys)
        assert ("deepseek-v4-pro", "GEN-L2-cross-ref-lookup-08") in skipped
        assert len(items) == 2  # the two non-empty arms

    def test_no_arm_info_in_items(self, tmp_path):
        raw, batch, keys = self._fixture(tmp_path)
        items, _sealed, _ = build_blind_set(raw, batch, keys)
        for it in items:
            assert set(it) == {"item_id", "case", "prompt", "rubric", "model_answer"}
            assert "arm" not in it

    def test_sealed_key_round_trips(self, tmp_path):
        raw, batch, keys = self._fixture(tmp_path)
        items, sealed, _ = build_blind_set(raw, batch, keys)
        # every item maps to exactly one (case, arm)
        for it in items:
            assert it["item_id"] in sealed
            assert sealed[it["item_id"]]["case"] == it["case"]
        assert len(sealed) == len(items)

    def test_leak_scan_clean_on_structural_fields(self, tmp_path):
        raw, batch, keys = self._fixture(tmp_path)
        items, _sealed, _ = build_blind_set(raw, batch, keys)
        # model_answer may name a model, but structural fields must be clean
        assert leak_scan(items) == []

    def test_leak_scan_flags_arm_token_in_prompt(self, tmp_path):
        raw, batch, keys = self._fixture(tmp_path)
        # poison the prompt with an arm token
        batch.write_text(
            json.dumps(
                {"case": "GEN-L2-cross-ref-lookup-08", "prompt": "ask claude to count"}
            )
            + "\n"
        )
        items, _sealed, _ = build_blind_set(raw, batch, keys)
        assert leak_scan(items), "should flag 'claude' leaking into the prompt"


class TestAlphaWiring:
    def test_perfect_agreement_alpha_one(self):
        from services.governance.iaa import krippendorff_alpha_nominal

        # two raters, identical labels across items -> alpha 1.0
        items = [["correct", "correct"], ["wrong", "wrong"], ["partial", "partial"]]
        assert krippendorff_alpha_nominal(items) == pytest.approx(1.0)

    def test_band_for_high_alpha(self):
        from services.governance.iaa import landis_koch_band

        assert landis_koch_band(0.85) == "almost perfect"
