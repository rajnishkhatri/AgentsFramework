"""L1-purity tests for components/answer_verifiers.py — the deterministic half
of the GoalJudge correctness cascade.

`verify_answer` is a PURE, reference-free function: given the task text, the
final answer, and the tool trajectory, it returns ``True`` (result is correct),
``False`` (result ran but is wrong), or ``None`` (no checkable shape / cannot
parse confidently → defer to the LLM judge). No LLM, no I/O — so these are
exact, zero-flake assertions (TDD Protocol A, uncertainty=ZERO).

Why this exists: the GoalJudge-vs-seed measurement found the judge scored a
REVERSED topological sort goal_met=1.0 ("respects all dependencies") while
failing a CORRECT one for not echoing it. The judge grades process-presence,
never result-correctness. This verifier owns correctness on checkable shapes so
a confidently-wrong order can no longer pass.

Anti-patterns avoided:
  - Tautological (TAP-1): tests assert the BEHAVIOURAL property (reversed order
    is rejected, correct order accepted) against known-good/known-bad vectors —
    they never reimplement Kahn's algorithm and compare.
  - Gap Blindness (TAP-6): the REJECTION test (wrong order → False) and the
    ABSTAIN test (unparseable → None) come before the acceptance test.
  - Determinism Theater (TAP-3): no LLM, no string-matching on model prose.
"""

from __future__ import annotations

import pytest

from components.answer_verifiers import verify_answer

# The real GEN-L2-dependency-resolve-12 task text + fixture edges
# (A->B, A->C, B->D, C->D ⇒ correct install order is D, B, C, A).
TOPO_TASK = (
    "Read /workspace/deps.txt where each line is 'A -> B' meaning A depends on "
    "B. Produce a valid install order (a topological sort) such that every "
    "dependency is installed before the thing that needs it, and report the "
    "order. If there is a cycle, report which nodes form it instead."
)
DEPS_EVIDENCE = [
    {
        "tool_name": "read_file",
        "tool_input": {"path": "/workspace/deps.txt"},
        "tool_output": "A -> B\nA -> C\nB -> D\nC -> D\n",
    }
]


def _answer(order_text: str) -> str:
    return f"The install order is: {order_text}"


# ─────────────────────────────────────────────────────────────────────
# FAILURE PATH FIRST (TAP-4 / TAP-6): a wrong result must be rejected.
# These are the two missed-failures (340b0ddf, 6bc71fa5) the seed caught.
# ─────────────────────────────────────────────────────────────────────


class TestTopoRejection:
    def test_reversed_order_is_wrong(self):
        # A,B,C,D installs A first — violates every edge. The judge passed this
        # at 1.0; the verifier must return False.
        verdict = verify_answer(TOPO_TASK, _answer("A, B, C, D"), DEPS_EVIDENCE)
        assert verdict is False

    def test_partial_violation_is_wrong(self):
        # D, A, B, C: A before B and C — still violates A's deps.
        verdict = verify_answer(TOPO_TASK, _answer("D, A, B, C"), DEPS_EVIDENCE)
        assert verdict is False


class TestTopoAbstain:
    """A parse miss must DEFER to the LLM (None), never emit a false fail."""

    def test_unparseable_answer_abstains(self):
        verdict = verify_answer(TOPO_TASK, "I read the file and sorted it.", DEPS_EVIDENCE)
        assert verdict is None

    def test_missing_evidence_abstains(self):
        # No deps available anywhere → cannot validate → defer.
        verdict = verify_answer(TOPO_TASK, _answer("D, B, C, A"), evidence=None)
        assert verdict is None

    def test_non_checkable_task_abstains(self):
        verdict = verify_answer(
            "Summarise the key claim of the attached paper in two sentences.",
            "The paper argues that X causes Y.",
            evidence=None,
        )
        assert verdict is None

    def test_answer_with_unknown_node_abstains(self):
        # Mentions a node not in the graph → we cannot be sure we parsed the
        # order correctly → defer rather than guess.
        verdict = verify_answer(TOPO_TASK, _answer("D, B, C, A, Z"), DEPS_EVIDENCE)
        assert verdict is None


# ─────────────────────────────────────────────────────────────────────
# ACCEPTANCE: a correct result is accepted — including the one the judge
# WRONGLY failed for not echoing (f64ba868), as long as the order is present.
# ─────────────────────────────────────────────────────────────────────


class TestTopoRealWorldFormat:
    """Regression vectors copied from the ACTUAL stored arm answers (the offline
    proof against the frozen seed). They use the Unicode arrow ``→`` and write
    the order as an arrow-joined chain — the format the synthetic fixtures
    missed, which caused the verifier to abstain on every real fn. A fix that
    passes the synthetic tests but abstains here does NOT fix the missed-failures.
    """

    # haiku 340b0ddf + opus 6bc71fa5: reversed chain, the two missed-failures.
    def test_real_reversed_unicode_chain_is_wrong(self):
        answer = (
            "FINAL ANSWER:\n\n**Input Dependencies:**\n- A → B\n- A → C\n- B → D\n"
            "- C → D\n\n**Topological Sort Result:**\n```\nA → B → C → D\n```\n"
        )
        assert verify_answer(TOPO_TASK, answer, DEPS_EVIDENCE) is False

    # flash f64ba868: correct order, newline-listed — the false-downgrade.
    def test_real_correct_newline_list_is_right(self):
        answer = (
            "FINAL ANSWER: Finished — topological ordering written:\n\n"
            "```\nD\nB\nC\nA\n```\n\n**Reasoning:** From the dependency graph:\n"
            "- A → B, A → C\n- B → D\n- C → D\n"
        )
        assert verify_answer(TOPO_TASK, answer, DEPS_EVIDENCE) is True


class TestTopoAcceptance:
    def test_correct_order_dbca(self):
        assert verify_answer(TOPO_TASK, _answer("D, B, C, A"), DEPS_EVIDENCE) is True

    def test_correct_order_dcba_interchangeable(self):
        # B/C are interchangeable (both depend only on D) — D, C, B, A is also valid.
        assert verify_answer(TOPO_TASK, _answer("D, C, B, A"), DEPS_EVIDENCE) is True

    def test_edges_read_from_task_text_when_no_evidence(self):
        # If the answer restates the edges, the verifier can still validate
        # without the tool trajectory.
        answer = "Dependencies: A -> B, A -> C, B -> D, C -> D. Install order: D, B, C, A"
        assert verify_answer(TOPO_TASK, answer, evidence=None) is True
