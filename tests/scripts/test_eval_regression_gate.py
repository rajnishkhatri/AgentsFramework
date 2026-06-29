"""L2 tests for scripts/eval_regression_gate.py (harness v2 plan, item 4.3).

No live LLM — the gate grades a synthetic evals.log snapshot. Failure paths first
(TAP-4): a frozen regression eval that drops below the floor must FAIL the gate;
only then the all-pass case. Also covers the pure regression_rows() selector and
the "no regression rows -> nothing to gate" early return.
"""

from __future__ import annotations

import json
import uuid

from scripts.eval_regression_gate import (
    pass_rates_from_eval_log,
    regression_rows,
    run_gate,
)

# Three deterministic GEN-L1 cases used as the frozen regression set under test.
_CASE_SUM = "GEN-L1-read-sum-01"
_CASE_FIELD = "GEN-L1-extract-field-13"


def _write_corpus(path, *, tiers: dict[str, str]) -> None:
    """Write a minimal corpus JSON with the given per-case tier tags."""
    rows = [
        {"case": case, "difficulty": "L1", "prompt": "p", "tier": tier}
        for case, tier in tiers.items()
    ]
    path.write_text(json.dumps(rows) + "\n")


def _write_eval_log(path, answers: dict[str, str]) -> None:
    lines = []
    for case, answer in answers.items():
        tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
        lines.append(
            json.dumps(
                {"target": "call_llm", "task_id": tid, "ai_response": answer, "step": 1}
            )
        )
    path.write_text("\n".join(lines) + "\n")


class TestRegressionRows:
    def test_selects_only_regression_tagged(self):
        corpus = [
            {"case": "a", "tier": "regression"},
            {"case": "b", "tier": "capability"},
            {"case": "c"},  # untagged -> capability default
        ]
        rows = regression_rows(corpus)
        assert [r["case"] for r in rows] == ["a"]


class TestPassRates:
    def test_correct_answer_is_pass(self, tmp_path):
        from scripts.seed_model_ab_workspace import EXPECTED_BY_CASE

        # The seeded read-sum answer is the integer file sum; emit the exact value.
        expected = EXPECTED_BY_CASE[_CASE_SUM].value
        log = tmp_path / "evals.log"
        _write_eval_log(log, {_CASE_SUM: f"The sum is {expected}."})
        rates = pass_rates_from_eval_log(log, [_CASE_SUM])
        assert rates[_CASE_SUM] == (1, 1)

    def test_missing_case_is_miss(self, tmp_path):
        log = tmp_path / "evals.log"
        _write_eval_log(log, {})  # empty log
        rates = pass_rates_from_eval_log(log, [_CASE_SUM])
        assert rates[_CASE_SUM] == (0, 1)


class TestRunGate:
    def test_regression_miss_fails_the_gate(self, tmp_path):
        corpus = tmp_path / "corpus.json"
        _write_corpus(corpus, tiers={_CASE_SUM: "regression"})
        log = tmp_path / "evals.log"
        _write_eval_log(log, {_CASE_SUM: "The sum is 999999."})  # wrong value
        assert run_gate(corpus, log) == 1

    def test_regression_did_not_run_fails_the_gate(self, tmp_path):
        corpus = tmp_path / "corpus.json"
        _write_corpus(corpus, tiers={_CASE_SUM: "regression"})
        log = tmp_path / "evals.log"
        _write_eval_log(log, {})  # the frozen eval never ran -> silent-gap violation
        assert run_gate(corpus, log) == 1

    def test_all_pass_passes_the_gate(self, tmp_path):
        from scripts.seed_model_ab_workspace import EXPECTED_BY_CASE

        corpus = tmp_path / "corpus.json"
        _write_corpus(
            corpus, tiers={_CASE_SUM: "regression", _CASE_FIELD: "regression"}
        )
        log = tmp_path / "evals.log"
        _write_eval_log(
            log,
            {
                _CASE_SUM: f"The sum is {EXPECTED_BY_CASE[_CASE_SUM].value}.",
                _CASE_FIELD: f"The name is {EXPECTED_BY_CASE[_CASE_FIELD].value}.",
            },
        )
        assert run_gate(corpus, log) == 0

    def test_no_regression_rows_is_a_pass(self, tmp_path):
        corpus = tmp_path / "corpus.json"
        _write_corpus(corpus, tiers={_CASE_SUM: "capability"})
        log = tmp_path / "evals.log"
        _write_eval_log(log, {})
        assert run_gate(corpus, log) == 0

    def test_missing_corpus_is_error(self, tmp_path):
        assert run_gate(tmp_path / "nope.json", tmp_path / "evals.log") == 2

    def test_real_corpus_has_a_regression_tier(self):
        # The committed corpus must carry the graduated L1 regression set so the
        # gate has something to watch (the 4.3 "machinery -> practice" assertion).
        import json as _json
        from pathlib import Path

        from scripts.eval_regression_gate import DEFAULT_CORPUS

        if not DEFAULT_CORPUS.exists():
            return  # corpus not built in this env; nothing to assert
        corpus = _json.loads(Path(DEFAULT_CORPUS).read_text())
        assert len(regression_rows(corpus)) >= 1
