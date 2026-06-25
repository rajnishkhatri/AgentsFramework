"""Answer-correctness scorer for the model-A/B GEN-L1 corpus (A3b).

The planning scorer (analyze_planning_traces.score_run) measures planning-CONTROL
behavior, not answer QUALITY — design doc §6 RC1. A model A/B needs to grade the
model's actual OUTPUT against a known expected value. This module does that for the
deterministic GEN-L1 cases (seed_model_ab_workspace.EXPECTED_BY_CASE).

Data source: the per-arm ``evals.log`` snapshot that ``model_ab_eval._drive_arm``
writes (the eval-capture JSONL; the black-box recordings do NOT carry the answer
text). For each case we take the LAST ``target == "call_llm"`` record (the final
answer the agent produced) and grade it.

Empty-output handling (design doc F4/F9, R4): an empty/whitespace answer is NEVER
a silent pass. It is graded as ``no_answer`` and counts as a miss, distinguishing
tokens==0 ("silent/budget") from tokens>0 ("all-thinking"). The summary keeps both
so the verdict path can HOLD on a regression and the report can name the cause.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.seed_model_ab_workspace import EXPECTED_BY_CASE, ExpectedAnswer


@dataclass
class CaseScore:
    case: str
    expected: str
    kind: str
    answer: str
    correct: bool
    outcome: str  # "correct" | "wrong" | "no_answer_silent" | "no_answer_thinking" | "missing"
    tokens_out: int | None = None


@dataclass
class AnswerSummary:
    """Per-arm answer-quality result. ``accuracy`` is the headline; the outcome
    breakdown is the evidence the report prints."""

    n: int
    correct: int
    scores: list[CaseScore] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return (self.correct / self.n) if self.n else 0.0

    @property
    def errored(self) -> int:
        """Cases whose answer was a provider/transport failure (not a model miss)."""
        return sum(1 for s in self.scores if s.outcome == "errored")

    @property
    def contaminated(self) -> bool:
        """True if ANY case errored — the run's accuracy is not a valid model
        signal and must be reported CONTAMINATED, not as a low score."""
        return self.errored > 0

    def outcomes(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.scores:
            out[s.outcome] = out.get(s.outcome, 0) + 1
        return out


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _all_numbers(text: str) -> list[float]:
    """Every number in the text. We scan ALL of them (not just the last) because
    models often append context after the answer — e.g. '8.0467 km (1 mile =
    1.60934 km)' — so a 'last number' heuristic would grab the conversion factor,
    not the result (an A3b false-negative found on the L1 sweep). The grader passes
    if ANY extracted number is within tolerance of the expected value."""
    out: list[float] = []
    for m in _NUM_RE.findall(text.replace(",", "")):
        try:
            out.append(float(m))
        except ValueError:
            continue
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s,]+", " ", s.lower()).strip()


# Provider/transport failures — NOT a model-quality signal. A run with these must
# be flagged CONTAMINATED, never scored as 0.0 accuracy (a DeepSeek/Anthropic
# outage or rate-limit is not "the model got the answer wrong"). Found on the N=3
# sweep: sustained sequential load tripped `litellm.InternalServerError:
# DeepseekException - Cannot connect` on every step, collapsing runs to fake 0.0.
_PROVIDER_ERROR_MARKERS = (
    "error: litellm",
    "litellm.",
    "internalservererror",
    "deepseekexception",
    "cannot connect",
    "rate limit",
    "ratelimiterror",
    "apiconnectionerror",
    "service unavailable",
    "overloaded",
)


def is_provider_error(answer: str) -> bool:
    a = (answer or "").lower()
    return any(m in a for m in _PROVIDER_ERROR_MARKERS)


# An answer that admits the task did NOT complete must never grade correct, even
# if it happens to contain the expected token (the prompt-leak false-positive:
# write-readback-06's apology contains 'ready' because 'ready' is in the prompt;
# the gave-up baseline answers contain leaked tokens too). These phrases are
# strong "I failed / couldn't do it" signals — distinct from a confident answer.
_FAILURE_PHRASES = (
    "i attempted", "i was unable", "unable to", "could not", "couldn't",
    "i encountered error", "encountered errors", "i don't see", "i cannot",
    "i can't", "outside the allowed", "no such file", "does not exist",
    "i could not", "please provide", "please upload",
)


def _admits_failure(answer: str) -> bool:
    a = answer.lower()
    return any(p in a for p in _FAILURE_PHRASES)


def _grade(answer: str, exp: ExpectedAnswer) -> bool:
    # Guard (both kinds): an answer that admits non-completion can't be correct
    # even if it contains the expected token/number (prompt-leak false-positive).
    if _admits_failure(answer):
        return False

    if exp.kind == "numeric":
        try:
            want = float(exp.value)
        except ValueError:
            return False
        tol = max(exp.tol, 0.0)
        # Pass if ANY number in the answer matches (handles trailing context).
        return any(abs(got - want) <= tol for got in _all_numbers(answer))

    # substring. For a comma-list expected ('apple, banana, cherry, date'), a
    # correct answer may reformat it (numbered/vertical/different separators), so
    # match by TOKEN-SET membership: every expected token must appear in the
    # answer. Falls back to a contiguous-substring match for single-token expects.
    exp_tokens = [t for t in re.split(r"[\s,]+", exp.value.lower()) if t]
    norm_answer = _norm(answer)
    if len(exp_tokens) > 1:
        return all(tok in norm_answer for tok in exp_tokens)
    return _norm(exp.value) in norm_answer


def _final_answers_by_case(eval_log: Path) -> dict[str, tuple[str, int | None]]:
    """Map case_id -> (final call_llm answer text, tokens_out).

    Keys eval records by ``task_id`` which == ``uuid5(NAMESPACE_DNS, case).hex``
    (run_case sets task_id = that trace_id). We resolve case→task_id via the same
    uuid5 the drive uses, so the join is exact.
    """
    import uuid

    records: list[dict] = []
    for line in eval_log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # non-JSON log noise

    # task_id -> last call_llm record
    last_call: dict[str, dict] = {}
    for r in records:
        if r.get("target") != "call_llm":
            continue
        tid = r.get("task_id", "")
        if tid:
            last_call[tid] = r  # later overwrites earlier => the final step wins

    out: dict[str, tuple[str, int | None]] = {}
    for case in EXPECTED_BY_CASE:
        tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
        rec = last_call.get(tid)
        if rec is None:
            continue
        resp = rec.get("ai_response", "")
        text = resp if isinstance(resp, str) else json.dumps(resp)
        out[case] = (text, rec.get("tokens_out"))
    return out


def score_answers(eval_log: Path, cases: list[str] | None = None) -> AnswerSummary:
    """Grade one arm's GEN-L1 answers from its eval-log snapshot."""
    answers = _final_answers_by_case(eval_log)
    target_cases = cases or list(EXPECTED_BY_CASE.keys())
    scores: list[CaseScore] = []
    for case in target_cases:
        exp = EXPECTED_BY_CASE.get(case)
        if exp is None:
            continue
        if case not in answers:
            scores.append(CaseScore(case, exp.value, exp.kind, "", False, "missing"))
            continue
        text, toks = answers[case]
        if is_provider_error(text):
            # Provider/transport failure — contaminates the run, not a model miss.
            scores.append(CaseScore(case, exp.value, exp.kind, text[:160], False,
                                    "errored", toks))
            continue
        if not text or not text.strip():
            outcome = "no_answer_thinking" if (toks or 0) > 0 else "no_answer_silent"
            scores.append(CaseScore(case, exp.value, exp.kind, "", False, outcome, toks))
            continue
        ok = _grade(text, exp)
        scores.append(
            CaseScore(case, exp.value, exp.kind, text[:160], ok,
                      "correct" if ok else "wrong", toks)
        )
    correct = sum(1 for s in scores if s.correct)
    return AnswerSummary(n=len(scores), correct=correct, scores=scores)


def score_mixed(eval_log: Path, cases: list[str]) -> AnswerSummary:
    """Grade a mixed L1/L2/L3 corpus: deterministic EXPECTED match for cases in
    the EXPECTED table (L1), GoalJudge ``goal_met`` for the rest (L2/L3 prose
    answers). Combines into one summary preserving the input case order."""
    det_cases = [c for c in cases if c in EXPECTED_BY_CASE]
    judge_cases = [c for c in cases if c not in EXPECTED_BY_CASE]
    det = score_answers(eval_log, cases=det_cases) if det_cases else AnswerSummary(0, 0)
    jud = score_answers_goaljudge(eval_log, judge_cases) if judge_cases else AnswerSummary(0, 0)
    by_case = {s.case: s for s in (*det.scores, *jud.scores)}
    ordered = [by_case[c] for c in cases if c in by_case]
    correct = sum(1 for s in ordered if s.correct)
    return AnswerSummary(n=len(ordered), correct=correct, scores=ordered)


def _goal_judge_by_case(eval_log: Path, cases: list[str]) -> dict[str, dict]:
    """Map case_id -> the GoalJudge ai_response dict (goal_met/criteria_met/...).

    GoalJudge runs once per case on the capable-tier evaluator; its record is
    keyed by the same task_id = uuid5(NAMESPACE_DNS, case).hex. Used for L2/L3
    rows whose ``want_answer`` is prose (no deterministic EXPECTED entry), so
    exact/substring matching doesn't apply — we defer to the judge's verdict."""
    import uuid

    last_judge: dict[str, dict] = {}
    for line in eval_log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("target") != "goal_judge":
            continue
        tid = r.get("task_id", "")
        resp = r.get("ai_response")
        if tid and isinstance(resp, dict):
            last_judge[tid] = resp  # last wins (final cycle)

    out: dict[str, dict] = {}
    for case in cases:
        tid = uuid.uuid5(uuid.NAMESPACE_DNS, case).hex
        if tid in last_judge:
            out[case] = last_judge[tid]
    return out


def score_answers_goaljudge(eval_log: Path, cases: list[str]) -> AnswerSummary:
    """Grade L2/L3 answers via the GoalJudge verdict (goal_met) instead of a
    deterministic EXPECTED match. ``correct`` == goal_met True; the per-case
    ``answer`` field carries the judge rationale + criteria_met for the report.

    A case with NO goal_judge record is ``missing`` (never a silent pass) — the
    same garbage-in posture as the deterministic scorer."""
    judged = _goal_judge_by_case(eval_log, cases)
    scores: list[CaseScore] = []
    for case in cases:
        verdict = judged.get(case)
        if verdict is None:
            scores.append(CaseScore(case, "goal_met", "goaljudge", "", False, "missing"))
            continue
        goal_met = bool(verdict.get("goal_met"))
        criteria = verdict.get("criteria_met")
        rationale = str(verdict.get("rationale", ""))[:160]
        scores.append(CaseScore(
            case, "goal_met", "goaljudge",
            f"criteria_met={criteria} :: {rationale}",
            goal_met,
            "correct" if goal_met else "wrong",
        ))
    correct = sum(1 for s in scores if s.correct)
    return AnswerSummary(n=len(scores), correct=correct, scores=scores)
