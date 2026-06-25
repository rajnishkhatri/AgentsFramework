"""L2 Reproducible: model-swap A/B harness (scripts/model_ab_eval.py).

No live LLM (skill testing-pyramid L1/L2). Failure / contamination paths FIRST
(TAP-4): the dangerous case is an arm that did NOT run on the model it claimed —
that must CONTAMINATE, never silently PROMOTE. Behavior-parity HOLD and the clean
PROMOTE follow.
"""
from __future__ import annotations

import json

import pytest

from scripts.model_ab_eval import (
    CONTAMINATED,
    HOLD,
    PROMOTE,
    build_report_payload,
    check_arm_integrity,
    corpus_hash,
    decide_verdict,
    diff_summaries,
    render_markdown,
    write_reports,
)


# ── fixtures ───────────────────────────────────────────────────────────────────


def _summary(*, depth=1.0, replan=1.0, esc_precision=1.0, esc_tp=2, esc_fp=0):
    """A score_run-shaped summary with two rate phases + an escalation matrix."""
    return {
        "phases": {
            "depth": {"n": 4, "scored": 4, "missing_trace": 0, "hits": 4,
                      "rate": depth, "mismatches": []},
            "replan": {"n": 3, "scored": 3, "missing_trace": 0, "hits": 3,
                       "rate": replan, "mismatches": []},
        },
        "escalation_confusion": {
            "tp": esc_tp, "fp": esc_fp, "tn": 1, "fn": 0,
            "precision": esc_precision, "recall": 1.0,
        },
        "fanout_confusion": {
            "tp": 0, "fp": 0, "tn": 0, "fn": 0, "precision": 1.0, "recall": 1.0,
        },
    }


def _step_executed(model: str, cost: float = 0.01):
    return {"event_type": "step_executed", "details": {"model": model, "cost_usd": cost}}


def _rows(n=2):
    return [
        {"case": f"C{i}", "gj_id": "", "phase": "depth", "trace_id": f"t{i}"}
        for i in range(n)
    ]


# ── integrity guard (governance: zero/wrong carrier on model identity) ─────────


class TestArmIntegrity:
    def test_wrong_model_is_contamination(self):
        rows = _rows(2)
        events = {
            "C0": [_step_executed("gpt-4o-mini")],
            "C1": [_step_executed("claude-haiku-4-5")],  # stray — not the pin
        }
        result = check_arm_integrity(rows, events, {"gpt-4o-mini"})
        assert result.ok is False
        assert any("WRONG-MODEL" in m and "C1" in m for m in result.mismatches)

    def test_empty_model_carrier_is_contamination_not_silent_pass(self):
        """The token-seam failure mode: a row that recorded NO model. Must fail,
        never count as a clean run."""
        rows = _rows(1)
        events = {"C0": [{"event_type": "step_executed", "details": {"cost_usd": 0.0}}]}
        result = check_arm_integrity(rows, events, {"gpt-4o-mini"})
        assert result.ok is False
        assert any("EMPTY-MODEL" in m for m in result.mismatches)

    def test_no_scored_rows_is_contamination(self):
        """An arm that produced no recordings at all ran nothing — contaminated."""
        rows = _rows(2)
        result = check_arm_integrity(rows, {"C0": [], "C1": []}, {"gpt-4o-mini"})
        assert result.ok is False
        assert result.rows_scored == 0

    def test_set_arm_accepts_any_name_in_the_set(self):
        """A set arm's expected roster is the whole set — Auto may route across
        tiers, so different rows running different set members is fine."""
        rows = _rows(2)
        events = {
            "C0": [_step_executed("claude-haiku-4-5")],
            "C1": [_step_executed("claude-sonnet-4-6")],
        }
        roster = {"claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"}
        result = check_arm_integrity(rows, events, roster)
        assert result.ok is True
        assert result.rows_scored == 2

    def test_clean_pinned_arm_passes(self):
        rows = _rows(2)
        events = {
            "C0": [_step_executed("gpt-4o-mini")],
            "C1": [_step_executed("gpt-4o-mini")],
        }
        result = check_arm_integrity(rows, events, {"gpt-4o-mini"})
        assert result.ok is True


# ── diff + verdict ─────────────────────────────────────────────────────────────


class TestDiffSummaries:
    def test_promote_when_candidate_matches_or_beats_every_phase(self):
        diff = diff_summaries(_summary(), _summary(depth=1.0, replan=1.0))
        assert diff["verdict"] == PROMOTE
        assert diff["regressions"] == []

    def test_hold_names_the_regressed_phase(self):
        base = _summary(depth=1.0)
        cand = _summary(depth=0.5)  # depth regressed
        diff = diff_summaries(base, cand)
        assert diff["verdict"] == HOLD
        assert any("depth" in r for r in diff["regressions"])

    def test_escalation_precision_drop_holds(self):
        base = _summary(esc_precision=1.0, esc_tp=2, esc_fp=0)
        cand = _summary(esc_precision=0.5, esc_tp=1, esc_fp=1)  # a false fan-out
        diff = diff_summaries(base, cand)
        assert diff["verdict"] == HOLD
        assert any("escalation precision" in r for r in diff["regressions"])

    def test_recall_drop_alone_still_promotes(self):
        """Recall is deliberately NOT gated (a missed escalation is the cheap
        error). Same precision, lower recall => still PROMOTE."""
        base = _summary(esc_precision=1.0, esc_tp=2, esc_fp=0)
        base["escalation_confusion"]["recall"] = 1.0
        cand = _summary(esc_precision=1.0, esc_tp=2, esc_fp=0)
        cand["escalation_confusion"]["recall"] = 0.5  # recall dropped only
        diff = diff_summaries(base, cand)
        assert diff["verdict"] == PROMOTE

    def test_tolerance_allows_small_dip(self):
        base = _summary(depth=1.0)
        cand = _summary(depth=0.95)
        assert diff_summaries(base, cand, tolerance=0.0)["verdict"] == HOLD
        assert diff_summaries(base, cand, tolerance=0.1)["verdict"] == PROMOTE

    def test_cost_never_auto_holds_without_cap(self):
        diff = diff_summaries(
            _summary(), _summary(), cost_baseline=1.0, cost_candidate=5.0, n_tasks=10
        )
        assert diff["verdict"] == PROMOTE  # 5x cost, but no behavior regression
        assert diff["cost"]["ratio"] == 5.0
        assert diff["cost"]["candidate_per_task_usd"] == 0.5

    def test_max_cost_ratio_opts_into_a_hard_cap(self):
        diff = diff_summaries(
            _summary(), _summary(),
            cost_baseline=1.0, cost_candidate=5.0, n_tasks=10, max_cost_ratio=2.0,
        )
        assert diff["verdict"] == HOLD
        assert any("cost ratio" in r for r in diff["regressions"])


class TestDecideVerdict:
    def _clean(self):
        return check_arm_integrity(
            _rows(1), {"C0": [_step_executed("m")]}, {"m"}
        )

    def _dirty(self):
        return check_arm_integrity(
            _rows(1), {"C0": [_step_executed("other")]}, {"m"}
        )

    def test_contaminated_dominates_a_clean_diff(self):
        diff = diff_summaries(_summary(), _summary())  # PROMOTE behavior
        verdict = decide_verdict(diff, self._clean(), self._dirty())
        assert verdict == CONTAMINATED  # never PROMOTE on a dirty arm

    def test_contaminated_reported_separately_from_hold(self):
        """Instrumentation failure (CONTAMINATED) is NOT collapsed into a real
        behavior regression (HOLD) — the governance instrumentation/outcome split."""
        diff = diff_summaries(_summary(depth=1.0), _summary(depth=0.0))  # HOLD
        # both arms clean -> the HOLD stands (not masked as CONTAMINATED)
        assert decide_verdict(diff, self._clean(), self._clean()) == HOLD
        # a dirty arm -> CONTAMINATED regardless of the behavior HOLD
        assert decide_verdict(diff, self._dirty(), self._clean()) == CONTAMINATED

    def test_both_clean_passes_through_behavior_verdict(self):
        diff = diff_summaries(_summary(), _summary())
        assert decide_verdict(diff, self._clean(), self._clean()) == PROMOTE


# ── report writers (governance: decision artifact + verbatim evidence) ─────────


class TestReportWriters:
    def _payload(self, tmp_path, verdict=PROMOTE):
        corpus = tmp_path / "corpus.jsonl"
        corpus.write_text(json.dumps({"case": "C0"}) + "\n")
        base_integ = check_arm_integrity(
            _rows(1), {"C0": [_step_executed("gpt-4o-mini")]}, {"gpt-4o-mini"}
        )
        cand_integ = check_arm_integrity(
            _rows(1), {"C0": [_step_executed("claude-haiku-4-5")]}, {"claude-haiku-4-5"}
        )
        diff = diff_summaries(_summary(), _summary(), n_tasks=1)
        return build_report_payload(
            run_id="testrun",
            corpus_path=corpus,
            baseline_arm="gpt-4o-mini",
            candidate_arm="claude-haiku-4-5",
            baseline_summary=_summary(),
            candidate_summary=_summary(),
            diff=diff,
            verdict=verdict,
            baseline_integrity=base_integ,
            candidate_integrity=cand_integ,
            n_tasks=1,
        )

    def test_json_has_both_summaries_verdict_and_corpus_hash(self, tmp_path):
        payload = self._payload(tmp_path)
        md_path, json_path = write_reports(tmp_path / "out", payload)
        data = json.loads(json_path.read_text())
        assert data["verdict"] == PROMOTE
        assert "baseline" in data["summaries"] and "candidate" in data["summaries"]
        assert data["corpus_hash"] == corpus_hash(tmp_path / "corpus.jsonl")
        assert data["arms"]["baseline"] == "gpt-4o-mini"

    def test_markdown_leads_with_the_verdict_banner(self, tmp_path):
        payload = self._payload(tmp_path, verdict=HOLD)
        md = render_markdown(payload)
        # The verdict appears in the first few lines (banner-first contract).
        head = "\n".join(md.splitlines()[:6])
        assert "HOLD" in head
        assert "VERDICT: HOLD" in md

    def test_markdown_lists_per_row_mismatch_evidence_when_contaminated(self, tmp_path):
        corpus = tmp_path / "corpus.jsonl"
        corpus.write_text(json.dumps({"case": "C0"}) + "\n")
        dirty = check_arm_integrity(
            _rows(1), {"C0": [_step_executed("ghost-model")]}, {"gpt-4o-mini"}
        )
        clean = check_arm_integrity(
            _rows(1), {"C0": [_step_executed("claude-haiku-4-5")]}, {"claude-haiku-4-5"}
        )
        diff = diff_summaries(_summary(), _summary(), n_tasks=1)
        payload = build_report_payload(
            run_id="r", corpus_path=corpus,
            baseline_arm="gpt-4o-mini", candidate_arm="claude-haiku-4-5",
            baseline_summary=_summary(), candidate_summary=_summary(),
            diff=diff, verdict=CONTAMINATED,
            baseline_integrity=dirty, candidate_integrity=clean, n_tasks=1,
        )
        md = render_markdown(payload)
        assert "WRONG-MODEL" in md  # the verbatim per-row evidence
        assert "LIMIT:" in md  # the local-only honesty note is always stamped

    def test_local_limit_note_always_present(self, tmp_path):
        payload = self._payload(tmp_path)
        assert "FINAL gate" in payload["limit"]
        assert "LIMIT:" in render_markdown(payload)


# ── --gate exit codes ──────────────────────────────────────────────────────────


class TestGateExit:
    """``--gate`` exits non-zero on HOLD/CONTAMINATED, zero on PROMOTE. Driven
    through main() in --score-only mode against synthetic recordings so no LLM
    runs."""

    def _write_arm(self, run_dir, arm, model, *, cost):
        rec = run_dir / arm / "recordings" / "wf0"
        rec.mkdir(parents=True, exist_ok=True)
        # One STEP_EXECUTED carrier + a STEP_PLANNED depth carrier so the phase
        # scores. The case/workflow id must match the corpus row's trace_id.
        events = [
            {"event_type": "step_planned", "details": {"planning_depth": "L0"}},
            {"event_type": "step_executed", "details": {"model": model, "cost_usd": cost}},
        ]
        (rec / "trace.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events)
        )

    def _corpus(self, tmp_path):
        corpus = tmp_path / "corpus.jsonl"
        corpus.write_text(
            json.dumps(
                {"case": "wf0", "gj_id": "", "phase": "depth",
                 "trace_id": "wf0", "want_depth": "L0", "prompt": "x"}
            )
            + "\n"
        )
        return corpus

    def test_gate_returns_zero_on_promote(self, tmp_path):
        from scripts.model_ab_eval import main

        corpus = self._corpus(tmp_path)
        run_dir = tmp_path / "ab" / "run1"
        self._write_arm(run_dir, "baseline", "gpt-4o-mini", cost=0.01)
        self._write_arm(run_dir, "candidate", "claude-haiku-4-5", cost=0.02)
        rc = main([
            "--score-only", "--gate",
            "--corpus", str(corpus),
            "--baseline", "gpt-4o-mini", "--candidate", "claude-haiku-4-5",
            "--out", str(tmp_path / "ab"), "--run-id", "run1",
        ])
        assert rc == 0

    def test_gate_returns_nonzero_on_contamination(self, tmp_path):
        from scripts.model_ab_eval import main

        corpus = self._corpus(tmp_path)
        run_dir = tmp_path / "ab" / "run2"
        # candidate ran the WRONG model -> contamination -> non-zero exit
        self._write_arm(run_dir, "baseline", "gpt-4o-mini", cost=0.01)
        self._write_arm(run_dir, "candidate", "ghost-model", cost=0.02)
        rc = main([
            "--score-only", "--gate",
            "--corpus", str(corpus),
            "--baseline", "gpt-4o-mini", "--candidate", "claude-haiku-4-5",
            "--out", str(tmp_path / "ab"), "--run-id", "run2",
        ])
        assert rc == 1


class TestRejectAllSetArm:
    """F2: the 'all' set is pin-only — a SET arm runs Auto, which would escalate
    into opus-4-8 on 'all'. ``--baseline-set all`` / ``--candidate-set all`` must
    be rejected with a non-zero exit BEFORE any drive/score work."""

    def _corpus(self, tmp_path):
        corpus = tmp_path / "corpus.jsonl"
        corpus.write_text(
            json.dumps(
                {"case": "wf0", "gj_id": "", "phase": "depth",
                 "trace_id": "wf0", "want_depth": "L0", "prompt": "x"}
            )
            + "\n"
        )
        return corpus

    def test_candidate_set_all_is_rejected(self, tmp_path):
        from scripts.model_ab_eval import main

        rc = main([
            "--score-only",
            "--corpus", str(self._corpus(tmp_path)),
            "--baseline-set", "openai", "--candidate-set", "all",
            "--out", str(tmp_path / "ab"), "--run-id", "r",
        ])
        assert rc == 2

    def test_baseline_set_all_is_rejected(self, tmp_path):
        from scripts.model_ab_eval import main

        rc = main([
            "--score-only",
            "--corpus", str(self._corpus(tmp_path)),
            "--baseline-set", "all", "--candidate-set", "deepseek",
            "--out", str(tmp_path / "ab"), "--run-id", "r",
        ])
        assert rc == 2

    def test_routable_set_arm_is_not_rejected_by_the_guard(self, tmp_path, capsys):
        # A routable set passes the F2 guard (it may fail later for other reasons,
        # but the all-set rejection MESSAGE must not appear).
        from scripts.model_ab_eval import main

        main([
            "--score-only",
            "--corpus", str(self._corpus(tmp_path)),
            "--baseline-set", "openai", "--candidate-set", "anthropic",
            "--out", str(tmp_path / "ab"), "--run-id", "r2",
        ])
        out = capsys.readouterr().out
        assert "is rejected" not in out, "routable set arm must not hit the F2 guard"

    def test_pinned_arm_naming_an_all_only_model_is_not_rejected(self, tmp_path, capsys):
        # A PINNED arm (not --*-set) reaches the 'all' set internally via
        # MODEL_PROFILE_SET so the pin resolves — the F2 guard must NOT fire.
        from scripts.model_ab_eval import main

        main([
            "--score-only",
            "--corpus", str(self._corpus(tmp_path)),
            "--baseline", "gpt-4o", "--candidate", "claude-opus-4-8",
            "--out", str(tmp_path / "ab"), "--run-id", "r3",
        ])
        out = capsys.readouterr().out
        assert "is rejected" not in out, "a pinned arm must not hit the F2 guard"
