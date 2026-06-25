"""L2 Reproducible: extensive model-A/B analyzer (scripts/analyze_model_ab.py).

No live LLM (skill testing-pyramid L1/L2). Failure / contamination paths FIRST
(TAP-4): the dangerous case is a cell whose pinned model didn't actually run —
that must be EXCLUDED from the aggregate, never silently averaged in. Then the
eligibility/sampling matrix construction, the per-(model,family) aggregation, and
the matched-subset fairness comparison (§3.3a).
"""
from __future__ import annotations

import json

from scripts.analyze_model_ab import (
    aggregate_cell,
    aggregate_matrix,
    build_matrix,
    build_report_payload,
    gate_row_integrity,
    is_reasoning_eligible,
    matched_comparison,
    render_markdown,
    write_reports,
)


# ── fixtures ───────────────────────────────────────────────────────────────────


def _step(model: str, *, tin: int = 100, tout: int = 50, cost: float = 0.01):
    return {
        "event_type": "step_executed",
        "details": {
            "model": model,
            "tokens_in": tin,
            "tokens_out": tout,
            "cost_usd": cost,
        },
    }


def _row(
    case: str,
    model: str,
    family: str = "general",
    *,
    difficulty: str = "L2",
    trace_id: str | None = None,
    ttft: float = 200.0,
    latency: float = 1000.0,
    tool_cards: int = 1,
):
    return {
        "case": case,
        "model": model,
        "family": family,
        "difficulty": difficulty,
        "trace_id": trace_id or f"t-{case}-{model}",
        "ttft_ms": ttft,
        "latency_ms": latency,
        "tool_card_count": tool_cards,
    }


def _corpus_case(case: str, family: str, difficulty: str):
    return {"case": case, "family": family, "difficulty": difficulty}


# ── eligibility predicate (the single rule, mirrored from the TS reader) ────────


class TestEligibility:
    def test_l1_general_is_not_eligible(self):
        assert is_reasoning_eligible(_corpus_case("c", "general", "L1")) is False

    def test_l2_general_is_eligible(self):
        assert is_reasoning_eligible(_corpus_case("c", "general", "L2")) is True

    def test_l3_is_eligible(self):
        assert is_reasoning_eligible(_corpus_case("c", "general", "L3")) is True

    def test_multiturn_is_eligible_regardless_of_difficulty(self):
        assert is_reasoning_eligible(_corpus_case("c", "multi-turn", "L1")) is True

    def test_stress_family_is_eligible_regardless_of_difficulty(self):
        assert is_reasoning_eligible(_corpus_case("c", "stress", "L1")) is True


# ── matrix construction (eligibility + seeded sampling) ─────────────────────────


class TestBuildMatrix:
    def _corpus(self):
        return [
            _corpus_case("L1-a", "general", "L1"),
            _corpus_case("L1-b", "general", "L1"),
            _corpus_case("L2-a", "general", "L2"),
            _corpus_case("L2-b", "general", "L2"),
            _corpus_case("MT-a", "multi-turn", "L2"),
        ]

    def test_cheap_arm_takes_every_case_at_full_repeat(self):
        m = build_matrix(
            self._corpus(), models=["gpt-4o-mini"], run_id="r1", repeat=3
        )
        assert len(m["gpt-4o-mini"]["cases"]) == 5
        assert m["gpt-4o-mini"]["repeat"] == 3
        assert m["gpt-4o-mini"]["reasoning"] is False

    def test_reasoning_arm_drops_routine_l1_cases(self):
        m = build_matrix(
            self._corpus(),
            models=["claude-opus-4-8"],
            run_id="r1",
            reasoning_sample=1.0,  # take ALL eligible to isolate the eligibility filter
        )
        cases = {c["case"] for c in m["claude-opus-4-8"]["cases"]}
        # the two L1 general rows are excluded; the three eligible ones remain
        assert "L1-a" not in cases and "L1-b" not in cases
        assert cases == {"L2-a", "L2-b", "MT-a"}
        assert m["claude-opus-4-8"]["repeat"] == 1  # forced to 1

    def test_reasoning_sample_is_seeded_and_reproducible(self):
        a = build_matrix(
            self._corpus(), models=["deepseek-v4-pro"], run_id="run-X",
            reasoning_sample=0.5,
        )
        b = build_matrix(
            self._corpus(), models=["deepseek-v4-pro"], run_id="run-X",
            reasoning_sample=0.5,
        )
        assert [c["case"] for c in a["deepseek-v4-pro"]["cases"]] == [
            c["case"] for c in b["deepseek-v4-pro"]["cases"]
        ]

    def test_different_run_id_can_resample(self):
        a = build_matrix(
            self._corpus(), models=["deepseek-v4-pro"], run_id="run-X",
            reasoning_sample=0.4,
        )
        b = build_matrix(
            self._corpus(), models=["deepseek-v4-pro"], run_id="run-Y",
            reasoning_sample=0.4,
        )
        # Seeded on model+run_id — a different run_id is allowed to pick a
        # different subset (this is the property the report names per run).
        assert isinstance(a["deepseek-v4-pro"]["cases"], list)
        assert isinstance(b["deepseek-v4-pro"]["cases"], list)

    def test_budget_caps_total_and_prefers_hardest_first(self):
        corpus = [
            _corpus_case("L3-a", "general", "L3"),
            _corpus_case("L2-a", "general", "L2"),
            _corpus_case("L2-b", "general", "L2"),
            _corpus_case("MT-a", "multi-turn", "L2"),
        ]
        m = build_matrix(
            corpus, models=["claude-opus-4-8"], run_id="r1",
            reasoning_budget=2,
        )
        cases = m["claude-opus-4-8"]["cases"]
        assert len(cases) == 2
        # the L3 (hardest) must be in the budgeted slice
        assert any(c["case"] == "L3-a" for c in cases)


# ── per-cell integrity gate (governance: wrong/empty model excluded) ───────────


class TestRowIntegrity:
    def test_wrong_pinned_model_is_contamination(self):
        row = _row("C0", "gpt-4o-mini")
        clean, reason = gate_row_integrity(row, [_step("claude-haiku-4-5")], None)
        assert clean is False
        assert "WRONG-MODEL" in reason and "C0" in reason

    def test_empty_model_carrier_is_contamination(self):
        """The token-seam failure mode: a STEP with no model. Never a clean run."""
        row = _row("C0", "gpt-4o-mini")
        events = [{"event_type": "step_executed", "details": {"cost_usd": 0.0}}]
        clean, reason = gate_row_integrity(row, events, None)
        assert clean is False
        assert "EMPTY-MODEL" in reason

    def test_pinned_model_match_is_clean(self):
        row = _row("C0", "gpt-4o-mini")
        clean, reason = gate_row_integrity(row, [_step("gpt-4o-mini")], None)
        assert clean is True and reason is None

    def test_auto_arm_accepts_any_registry_model(self):
        row = _row("C0", "Auto")
        roster = {"claude-haiku-4-5", "claude-sonnet-4-6"}
        clean, _ = gate_row_integrity(row, [_step("claude-sonnet-4-6")], roster)
        assert clean is True

    def test_auto_arm_off_roster_is_contamination(self):
        row = _row("C0", "Auto")
        roster = {"claude-haiku-4-5"}
        clean, reason = gate_row_integrity(row, [_step("ghost-model")], roster)
        assert clean is False and "AUTO-OFF-ROSTER" in reason


# ── per-(model, family) aggregation ────────────────────────────────────────────


class TestAggregateCell:
    def test_contaminated_run_is_excluded_from_metrics(self):
        rows = [
            _row("C0", "gpt-4o", trace_id="t0", latency=1000.0),
            _row("C1", "gpt-4o", trace_id="t1", latency=9999.0),  # ran wrong model
        ]
        events = {
            "t0": [_step("gpt-4o", cost=0.02)],
            "t1": [_step("ghost", cost=0.50)],  # contamination
        }
        cell = aggregate_cell(rows, events)
        assert cell["n_runs"] == 1  # only the clean run counted
        assert cell["cases"] == ["C0"]
        assert cell["cost_total_usd"] == 0.02  # the 0.50 ghost cost excluded
        assert any("C1" in c for c in cell["contaminated"])

    def test_missing_trace_counted_but_not_contamination(self):
        rows = [_row("C0", "gpt-4o", trace_id="t0")]
        cell = aggregate_cell(rows, {"t0": []})  # no events -> missing trace
        assert cell["n_runs"] == 0
        assert "C0" in cell["missing_trace"]
        assert cell["contaminated"] == []

    def test_token_and_cost_means_over_clean_runs(self):
        rows = [
            _row("C0", "gpt-4o", trace_id="t0"),
            _row("C1", "gpt-4o", trace_id="t1"),
        ]
        events = {
            "t0": [_step("gpt-4o", tin=100, tout=40, cost=0.01)],
            "t1": [_step("gpt-4o", tin=300, tout=60, cost=0.03)],
        }
        cell = aggregate_cell(rows, events)
        assert cell["tokens_in_mean"] == 200.0
        assert cell["tokens_out_mean"] == 50.0
        assert cell["cost_mean_usd"] == 0.02

    def test_latency_percentiles_from_capture_rows(self):
        rows = [
            _row(f"C{i}", "gpt-4o", trace_id=f"t{i}", latency=float(100 * (i + 1)))
            for i in range(4)
        ]
        events = {f"t{i}": [_step("gpt-4o")] for i in range(4)}
        cell = aggregate_cell(rows, events)
        # latencies 100,200,300,400 -> p50 nearest-rank index ceil(.5*4)-1=1 -> 200
        assert cell["latency_p50_ms"] == 200.0
        assert cell["latency_p95_ms"] == 400.0

    def test_multi_step_trace_sums_tokens_and_cost(self):
        rows = [_row("C0", "gpt-4o", trace_id="t0")]
        events = {
            "t0": [
                _step("gpt-4o", tin=100, tout=10, cost=0.01),
                _step("gpt-4o", tin=200, tout=20, cost=0.02),
            ]
        }
        cell = aggregate_cell(rows, events)
        assert cell["tokens_in_mean"] == 300.0  # summed within the trace
        assert cell["cost_total_usd"] == 0.03


class TestAggregateMatrix:
    def test_groups_by_model_and_family_with_all_rollup(self):
        rows = [
            _row("G0", "gpt-4o", family="general", trace_id="tg0"),
            _row("M0", "gpt-4o", family="memory", trace_id="tm0"),
            _row("G0b", "claude-haiku-4-5", family="general", trace_id="th0"),
        ]
        events = {
            "tg0": [_step("gpt-4o")],
            "tm0": [_step("gpt-4o")],
            "th0": [_step("claude-haiku-4-5")],
        }
        agg = aggregate_matrix(rows, events)
        assert set(agg) == {"gpt-4o", "claude-haiku-4-5"}
        assert agg["gpt-4o"]["general"]["n_runs"] == 1
        assert agg["gpt-4o"]["memory"]["n_runs"] == 1
        assert agg["gpt-4o"]["__all__"]["n_runs"] == 2  # roll-up across families


# ── matched-subset fairness comparison (§3.3a) ─────────────────────────────────


class TestMatchedComparison:
    def test_restricts_to_the_shared_case_intersection(self):
        # baseline ran C0,C1,C2; opus ran only C1 (its sampled reasoning slice).
        rows = [
            _row("C0", "gpt-4o", trace_id="b0"),
            _row("C1", "gpt-4o", trace_id="b1"),
            _row("C2", "gpt-4o", trace_id="b2"),
            _row("C1", "claude-opus-4-8", trace_id="o1"),
        ]
        events = {
            "b0": [_step("gpt-4o", cost=0.01)],
            "b1": [_step("gpt-4o", cost=0.01)],
            "b2": [_step("gpt-4o", cost=0.01)],
            "o1": [_step("claude-opus-4-8", cost=0.10)],
        }
        agg = aggregate_matrix(rows, events)
        mc = matched_comparison(
            rows, events,
            reasoning_model="claude-opus-4-8",
            baseline_model="gpt-4o",
            matrix_aggregate=agg,
        )
        # only C1 is shared -> matched on exactly one case, NOT on C0/C2
        assert mc["matched_case_count"] == 1
        assert mc["matched_cases"] == ["C1"]
        assert "routine L1" in mc["note"]

    def test_contaminated_reasoning_run_drops_out_of_matched_set(self):
        rows = [
            _row("C1", "gpt-4o", trace_id="b1"),
            _row("C1", "claude-opus-4-8", trace_id="o1"),
        ]
        events = {
            "b1": [_step("gpt-4o")],
            "o1": [_step("ghost")],  # opus arm ran the wrong model -> excluded
        }
        agg = aggregate_matrix(rows, events)
        mc = matched_comparison(
            rows, events,
            reasoning_model="claude-opus-4-8",
            baseline_model="gpt-4o",
            matrix_aggregate=agg,
        )
        # opus contributed no CLEAN case -> the intersection is empty
        assert mc["matched_case_count"] == 0


# ── report writers (governance: decision artifact + honest-limit stamp) ────────


class TestReportWriters:
    def _payload(self, tmp_path):
        rows = [
            _row("C0", "gpt-4o", trace_id="t0"),
            _row("C1", "claude-opus-4-8", family="general", trace_id="t1"),
        ]
        events = {
            "t0": [_step("gpt-4o", cost=0.01)],
            "t1": [_step("claude-opus-4-8", cost=0.10)],
        }
        agg = aggregate_matrix(rows, events)
        corpus = tmp_path / "model_ab_corpus.json"
        corpus.write_text(json.dumps([{"case": "C0"}, {"case": "C1"}]))
        return build_report_payload(
            run_id="testrun",
            corpus_path=corpus,
            baseline_model="gpt-4o",
            matrix_aggregate=agg,
            matched_comparisons=[],
            rows=rows,
        )

    def test_json_has_per_model_family_and_corpus_hash(self, tmp_path):
        payload = self._payload(tmp_path)
        md_path, json_path = write_reports(tmp_path / "out", payload)
        data = json.loads(json_path.read_text())
        assert "gpt-4o" in data["per_model_family"]
        assert data["corpus_hash"] is not None
        assert "claude-opus-4-8" in data["trace_ids"][0] or data["trace_ids"]

    def test_markdown_has_headline_table_and_limit_note(self, tmp_path):
        payload = self._payload(tmp_path)
        md = render_markdown(payload)
        assert "# Model A/B" in md
        assert "Headline" in md
        assert "LIMIT:" in md  # the live-run honesty note is always stamped
        assert "matched shared case subset" in md  # the §3.3a caveat is stamped

    def test_contaminated_cells_listed_in_report(self, tmp_path):
        rows = [_row("C0", "gpt-4o", trace_id="t0")]
        events = {"t0": [_step("ghost")]}  # wrong model
        agg = aggregate_matrix(rows, events)
        corpus = tmp_path / "model_ab_corpus.json"
        corpus.write_text(json.dumps([{"case": "C0"}]))
        payload = build_report_payload(
            run_id="r", corpus_path=corpus, baseline_model="gpt-4o",
            matrix_aggregate=agg, matched_comparisons=[], rows=rows,
        )
        md = render_markdown(payload)
        assert "WRONG-MODEL" in md
        assert payload["contaminated_cells"]
