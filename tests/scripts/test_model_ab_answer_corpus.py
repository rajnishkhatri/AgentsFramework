"""L1 tests for the A3b answer-corpus path: seed, converter, answer scorer.

No live LLM. Failure paths first (FD6)."""

from __future__ import annotations

import json
import uuid

import pytest

from scripts.convert_model_ab_corpus import ANSWER_PHASE, convert, write_jsonl
from scripts.model_ab_answer_score import (
    score_answers,
    score_answers_goaljudge,
    score_mixed,
)
from scripts.seed_model_ab_workspace import EXPECTED_BY_CASE, seed_workspace


class TestSeed:
    def test_seeds_every_referenced_file(self, tmp_path):
        ws = seed_workspace(tmp_path)
        for rel in ("nums/a.txt", "nums/b.txt", "nums/c.txt", "contact.txt",
                    "log.txt", "scores.csv", "distance.txt", "profile.json",
                    "words.txt", "n.txt", "access.log"):
            assert (ws / rel).exists(), f"missing fixture {rel}"

    def test_nums_sum_matches_expected_answer(self, tmp_path):
        ws = seed_workspace(tmp_path)
        total = sum(int((ws / "nums" / f).read_text()) for f in ("a.txt", "b.txt", "c.txt"))
        assert str(total) == EXPECTED_BY_CASE["GEN-L1-read-sum-01"].value

    def test_profile_name_matches_expected(self, tmp_path):
        ws = seed_workspace(tmp_path)
        name = json.loads((ws / "profile.json").read_text())["name"]
        assert name == EXPECTED_BY_CASE["GEN-L1-extract-field-13"].value

    def test_idempotent(self, tmp_path):
        seed_workspace(tmp_path)
        first = (tmp_path / "n.txt").read_text()
        seed_workspace(tmp_path)
        assert (tmp_path / "n.txt").read_text() == first


class TestConverter:
    def test_only_general_rows_survive(self):
        rows = convert()
        assert rows, "expected general rows"
        assert all(r["family"] == "general" for r in rows)
        # 19 general rows in the source corpus
        assert len(rows) == 19

    def test_every_row_has_phase_prompt_trace(self):
        for r in convert():
            assert r["phase"] == ANSWER_PHASE
            assert r["prompt"]
            assert r["trace_id"]
            assert r["case"]

    def test_multi_turn_and_memory_excluded(self):
        cases = {r["case"] for r in convert()}
        assert not any(c.startswith("MT-") for c in cases)
        assert not any(c.startswith("MEM-") for c in cases)

    def test_writes_loadable_jsonl(self, tmp_path):
        from scripts.model_ab_eval import load_corpus

        out = write_jsonl(convert(), tmp_path / "ui_batch.jsonl")
        loaded = load_corpus(out)  # must not KeyError on 'phase'
        assert len(loaded) == 19


class TestAnswerScorer:
    """The scorer reads a per-arm evals.log snapshot of call_llm ai_response."""

    def _write_eval_log(self, path, case_to_answer: dict[str, tuple[str, int]]):
        lines = []
        for case, (answer, toks) in case_to_answer.items():
            tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
            lines.append(json.dumps({
                "target": "call_llm", "task_id": tid,
                "ai_response": answer, "tokens_out": toks, "step": 1,
            }))
        path.write_text("\n".join(lines) + "\n")

    def test_numeric_answer_graded_correct(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-read-sum-01": ("The sum is 42.", 10)})
        s = score_answers(log, cases=["GEN-L1-read-sum-01"])
        assert s.correct == 1
        assert s.scores[0].outcome == "correct"

    def test_numeric_answer_wrong_value_is_miss(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-read-sum-01": ("The sum is 41.", 10)})
        s = score_answers(log, cases=["GEN-L1-read-sum-01"])
        assert s.correct == 0
        assert s.scores[0].outcome == "wrong"

    def test_numeric_rounding_tolerance(self, tmp_path):
        # 5 miles -> 8.0467 km -> 8.0; a model saying 8.05 is within tol=0.05
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-convert-unit-05": ("8.05 km", 10)})
        s = score_answers(log, cases=["GEN-L1-convert-unit-05"])
        assert s.correct == 1

    def test_substring_answer_graded_correct(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-lookup-format-02": ("The domain is example.com", 8)})
        s = score_answers(log, cases=["GEN-L1-lookup-format-02"])
        assert s.correct == 1

    def test_empty_answer_with_tokens_is_no_answer_thinking(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-read-sum-01": ("", 4096)})
        s = score_answers(log, cases=["GEN-L1-read-sum-01"])
        assert s.correct == 0
        assert s.scores[0].outcome == "no_answer_thinking"  # F9 class

    def test_empty_answer_zero_tokens_is_no_answer_silent(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-read-sum-01": ("", 0)})
        s = score_answers(log, cases=["GEN-L1-read-sum-01"])
        assert s.scores[0].outcome == "no_answer_silent"  # F3 budget/silent class

    def test_failure_admission_with_leaked_token_is_wrong(self, tmp_path):
        # write-readback-06 expects 'ready' (a word in the prompt). A FAILED write
        # that says "I attempted to write 'ready' but encountered errors" must NOT
        # grade correct just because 'ready' appears (the prompt-leak false-positive).
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-write-readback-06":
                                   ("I attempted to write 'ready' but encountered errors.", 20)})
        s = score_answers(log, cases=["GEN-L1-write-readback-06"])
        assert s.correct == 0
        assert s.scores[0].outcome == "wrong"

    def test_failure_admission_with_leaked_numeric_is_wrong(self, tmp_path):
        # bool-check-15 expects 'odd'; "I was unable to access the file" must fail
        # even though no token matches — the guard is kind-agnostic.
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-bool-check-15":
                                   ("I was unable to access the file at the path.", 15)})
        s = score_answers(log, cases=["GEN-L1-bool-check-15"])
        assert s.scores[0].outcome == "wrong"

    def test_confident_correct_answer_still_passes(self, tmp_path):
        # Guard must not create false-NEGATIVES: a real answer mentioning the value.
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-bool-check-15":
                                   ("The file contains 17, which is odd.", 12)})
        s = score_answers(log, cases=["GEN-L1-bool-check-15"])
        assert s.correct == 1

    def test_provider_error_is_errored_and_contaminates(self, tmp_path):
        # A litellm InternalServerError response is NOT a model miss — it's a
        # provider/transport failure. It must be outcome 'errored' and flag the
        # summary contaminated (so the run reads CONTAMINATED, not fake 0.0).
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {
            "GEN-L1-read-sum-01":
                ("Error: litellm.InternalServerError: DeepseekException - "
                 "Cannot connect", 0),
            "GEN-L1-lookup-format-02": ("example.com", 5),
        })
        s = score_answers(log, cases=["GEN-L1-read-sum-01", "GEN-L1-lookup-format-02"])
        outcomes = {sc.case: sc.outcome for sc in s.scores}
        assert outcomes["GEN-L1-read-sum-01"] == "errored"
        assert outcomes["GEN-L1-lookup-format-02"] == "correct"
        assert s.errored == 1
        assert s.contaminated is True

    def test_clean_run_is_not_contaminated(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {"GEN-L1-read-sum-01": ("42", 5)})
        s = score_answers(log, cases=["GEN-L1-read-sum-01"])
        assert s.errored == 0 and s.contaminated is False

    def test_missing_record_is_missing_not_silent_pass(self, tmp_path):
        log = tmp_path / "evals.log"
        log.write_text("")  # no records at all
        s = score_answers(log, cases=["GEN-L1-read-sum-01"])
        assert s.correct == 0
        assert s.scores[0].outcome == "missing"

    def test_accuracy_and_outcome_breakdown(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_eval_log(log, {
            "GEN-L1-read-sum-01": ("42", 5),                    # correct
            "GEN-L1-lookup-format-02": ("example.com", 5),      # correct
            "GEN-L1-count-lines-03": ("99", 5),                 # wrong
        })
        s = score_answers(log, cases=[
            "GEN-L1-read-sum-01", "GEN-L1-lookup-format-02", "GEN-L1-count-lines-03",
        ])
        assert s.n == 3 and s.correct == 2
        assert abs(s.accuracy - 2 / 3) < 1e-9
        assert s.outcomes() == {"correct": 2, "wrong": 1}


class TestGoalJudgeScorer:
    """L2/L3 grading via GoalJudge goal_met (prose answers, no exact match)."""

    def _write_judge_log(self, path, case_to_verdict):
        lines = []
        for case, (goal_met, criteria) in case_to_verdict.items():
            tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
            lines.append(json.dumps({
                "target": "goal_judge", "task_id": tid,
                "ai_response": {"goal_met": goal_met, "criteria_met": criteria,
                                "rationale": "ok" if goal_met else "missed"},
            }))
        path.write_text("\n".join(lines) + "\n")

    def test_goal_met_true_is_correct(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_judge_log(log, {"GEN-L2-multi-file-reconcile-07": (True, 1.0)})
        s = score_answers_goaljudge(log, ["GEN-L2-multi-file-reconcile-07"])
        assert s.correct == 1 and s.scores[0].outcome == "correct"

    def test_goal_met_false_is_wrong(self, tmp_path):
        log = tmp_path / "evals.log"
        self._write_judge_log(log, {"GEN-L2-multi-file-reconcile-07": (False, 0.4)})
        s = score_answers_goaljudge(log, ["GEN-L2-multi-file-reconcile-07"])
        assert s.correct == 0 and s.scores[0].outcome == "wrong"

    def test_no_judge_record_is_missing(self, tmp_path):
        log = tmp_path / "evals.log"
        log.write_text("")
        s = score_answers_goaljudge(log, ["GEN-L2-multi-file-reconcile-07"])
        assert s.scores[0].outcome == "missing"


class TestMixedScorer:
    """score_mixed: deterministic for L1 (EXPECTED), GoalJudge for L2/L3."""

    def test_mixed_l1_deterministic_l2_goaljudge(self, tmp_path):
        log = tmp_path / "evals.log"
        l1_case = "GEN-L1-read-sum-01"           # in EXPECTED -> deterministic
        l2_case = "GEN-L2-multi-file-reconcile-07"  # not in EXPECTED -> GoalJudge
        l1_tid = uuid.uuid5(uuid.NAMESPACE_DNS, l1_case).hex
        l2_tid = uuid.uuid5(uuid.NAMESPACE_DNS, l2_case).hex
        log.write_text("\n".join([
            json.dumps({"target": "call_llm", "task_id": l1_tid,
                        "ai_response": "The sum is 42.", "tokens_out": 5}),
            json.dumps({"target": "goal_judge", "task_id": l2_tid,
                        "ai_response": {"goal_met": True, "criteria_met": 1.0,
                                        "rationale": "ok"}}),
        ]) + "\n")
        s = score_mixed(log, cases=[l1_case, l2_case])
        assert s.n == 2 and s.correct == 2
        # order preserved
        assert [sc.case for sc in s.scores] == [l1_case, l2_case]
        assert s.scores[0].kind == "numeric"     # L1 path
        assert s.scores[1].kind == "goaljudge"    # L2 path


class TestAnswerVerdictWiring:
    """--answer-score makes answer accuracy the verdict, integrity still dominates.
    Driven through main() in --score-only mode against synthetic recordings +
    evals.log snapshots (no live LLM)."""

    def _corpus(self, tmp_path, cases):
        corpus = tmp_path / "corpus.jsonl"
        corpus.write_text("\n".join(
            json.dumps({"case": c, "gj_id": "", "phase": "answer",
                        "trace_id": c, "prompt": "x"})
            for c in cases
        ) + "\n")
        return corpus

    def _write_arm_recordings(self, run_dir, arm, model, cases):
        for c in cases:
            tid = uuid.uuid5(uuid.NAMESPACE_DNS, c).hex
            rec = run_dir / arm / "recordings" / tid
            rec.mkdir(parents=True, exist_ok=True)
            (rec / "trace.jsonl").write_text(
                json.dumps({"event_type": "step_executed",
                            "details": {"model": model, "cost_usd": 0.01}}) + "\n"
            )

    def _write_arm_eval_log(self, run_dir, arm, case_to_answer):
        lines = []
        for c, ans in case_to_answer.items():
            tid = uuid.uuid5(uuid.NAMESPACE_DNS, c).hex
            lines.append(json.dumps({
                "target": "call_llm", "task_id": tid,
                "ai_response": ans, "tokens_out": 10,
            }))
        (run_dir / arm).mkdir(parents=True, exist_ok=True)
        (run_dir / arm / "evals.log").write_text("\n".join(lines) + "\n")

    def test_promote_when_candidate_answer_accuracy_ge_baseline(self, tmp_path):
        from scripts.model_ab_eval import main

        cases = ["GEN-L1-read-sum-01", "GEN-L1-lookup-format-02"]
        corpus = self._corpus(tmp_path, cases)
        run_dir = tmp_path / "ab" / "r"
        self._write_arm_recordings(run_dir, "baseline", "gpt-4o-mini", cases)
        self._write_arm_recordings(run_dir, "candidate", "claude-haiku-4-5", cases)
        # baseline: 1/2; candidate: 2/2 -> PROMOTE
        self._write_arm_eval_log(run_dir, "baseline",
                                 {"GEN-L1-read-sum-01": "wrong 0",
                                  "GEN-L1-lookup-format-02": "example.com"})
        self._write_arm_eval_log(run_dir, "candidate",
                                 {"GEN-L1-read-sum-01": "42",
                                  "GEN-L1-lookup-format-02": "example.com"})
        rc = main([
            "--score-only", "--answer-score", "--gate",
            "--corpus", str(corpus),
            "--baseline", "gpt-4o-mini", "--candidate", "claude-haiku-4-5",
            "--out", str(tmp_path / "ab"), "--run-id", "r",
        ])
        assert rc == 0  # PROMOTE

    def test_hold_when_candidate_answer_accuracy_regresses(self, tmp_path):
        from scripts.model_ab_eval import main

        cases = ["GEN-L1-read-sum-01", "GEN-L1-lookup-format-02"]
        corpus = self._corpus(tmp_path, cases)
        run_dir = tmp_path / "ab" / "r2"
        self._write_arm_recordings(run_dir, "baseline", "gpt-4o-mini", cases)
        self._write_arm_recordings(run_dir, "candidate", "claude-haiku-4-5", cases)
        # baseline: 2/2; candidate: 1/2 -> HOLD (regression)
        self._write_arm_eval_log(run_dir, "baseline",
                                 {"GEN-L1-read-sum-01": "42",
                                  "GEN-L1-lookup-format-02": "example.com"})
        self._write_arm_eval_log(run_dir, "candidate",
                                 {"GEN-L1-read-sum-01": "wrong 0",
                                  "GEN-L1-lookup-format-02": "example.com"})
        rc = main([
            "--score-only", "--answer-score", "--gate",
            "--corpus", str(corpus),
            "--baseline", "gpt-4o-mini", "--candidate", "claude-haiku-4-5",
            "--out", str(tmp_path / "ab"), "--run-id", "r2",
        ])
        assert rc == 1  # HOLD

    def test_contamination_dominates_even_with_perfect_answers(self, tmp_path):
        from scripts.model_ab_eval import main

        cases = ["GEN-L1-read-sum-01"]
        corpus = self._corpus(tmp_path, cases)
        run_dir = tmp_path / "ab" / "r3"
        self._write_arm_recordings(run_dir, "baseline", "gpt-4o-mini", cases)
        # candidate ran the WRONG model -> contamination even if answer is right
        self._write_arm_recordings(run_dir, "candidate", "ghost-model", cases)
        self._write_arm_eval_log(run_dir, "baseline", {"GEN-L1-read-sum-01": "42"})
        self._write_arm_eval_log(run_dir, "candidate", {"GEN-L1-read-sum-01": "42"})
        rc = main([
            "--score-only", "--answer-score", "--gate",
            "--corpus", str(corpus),
            "--baseline", "gpt-4o-mini", "--candidate", "claude-haiku-4-5",
            "--out", str(tmp_path / "ab"), "--run-id", "r3",
        ])
        assert rc == 1  # CONTAMINATED
