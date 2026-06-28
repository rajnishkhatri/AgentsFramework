"""Offline tests for the CORRUPT-SUCCESS echo-softening (residual-fp fix).

Context — the two residual false-downgrades left after the deterministic
answer-verifier cascade (commit 463ac59) turned out to have DIFFERENT root
causes, both diagnosed from the judge's full 8192-char view (NOT the 500-char
harvest). See memory ``goaljudge-residual-fp-root-cause``:

  - ``70ff3369`` (GEN-L3-iterative-refine-15, budget-offset): the full answer DOES
    verify the offset — "The overrun is fully offset with no category cut below
    its actual spend." The CORRUPT-SUCCESS subtask decomposition over-fired,
    treating "verify the offset balances to zero" as a missing subtask because the
    answer phrased it "fully offset" rather than echoing "balances to zero". This
    is the **echo/phrasing false-downgrade** the semantic-satisfaction clause fixes.
  - ``df252d51`` (GEN-L3-multi-hop-synthesis-14, citation): the judge was RIGHT —
    the task asks to summarise the most-cited paper's *key claim*, and the answer
    gives Paper 3's *title* ("Foundations of locality") but never its claim
    ("Temporal locality dominates real workloads", which is in paper-3.txt). Both
    human raters graded it ``correct`` (lenient). This is a gold-label question,
    NOT a judge fix — the softening must NOT teach the judge to accept it.

Determinism boundary (AGENTS.md H1: no live LLM in CI). A prompt change's
behavioural effect cannot be re-measured offline, so these tests pin what IS
deterministic:
  1. the cascade routes BOTH cases to the LLM fallback (``verify_answer`` abstains —
     ``None`` — so the prompt is what judges them), and
  2. the rendered prompt now carries the semantic-satisfaction clause that lets a
     differently-phrased, evidence-corroborated outcome satisfy a subtask, WITHOUT
     deleting the corrupt-success / evidence-grounding guards.

LIVE RE-JUDGE FINDING (2026-06-26, scripts/revalidate_goaljudge_residual_fp.py,
claude-haiku-4-5 ×5; gpt-4o quota-exhausted): df252d51 correctly stays not-met 5/5
(the guard holds — title-not-claim still fails). 70ff3369 ALSO stays not-met 5/5
EVEN WITH the clause — the judge objects not to phrasing but to the answer's
genuinely-confusing verification PROSE ("total planned 880→850, matching actual 840
plus 10 remaining slack", which reads as self-contradictory though the underlying
math is correct). The clause relaxes wording, NOT distrust of incoherent prose — so
this is the clause working as designed, and 70ff3369 is a borderline lenient-label
case like df252d51, NOT a clean echo flip. Decision: accept the honest result, do
not over-soften. These tests therefore assert clause-presence + guards only; they do
NOT assert a goal_met flip (there is none to assert).

Anti-patterns avoided (research/tdd_agentic_systems_prompt.md):
  - Determinism Theater (TAP-3): no assertion on model-generated prose; we assert
    on the rendered *prompt* (a deterministic template) and on the deterministic
    cascade routing.
  - Gap Blindness (TAP-6): the guard tests (clause must NOT remove the
    corrupt-success markers; title-not-claim case must still reach the strict
    rubric) sit alongside the fix assertion.
"""

from __future__ import annotations

import pytest

from components.answer_verifiers import verify_answer
from components.goal_judge import GoalJudge, _summarize_evidence
from services.prompt_service import PromptService
from tests.components.test_goal_judge import FakeLLMService, _profile

# ── stored full answers (the 8192-char view the LIVE judge saw, pulled from the
#    per-arm evals.log goal_judge record — NOT the 500-char l2l3_raw_answers.json) ──

BUDGET_TASK = (
    "Read /workspace/budget.csv (category,planned,actual). Identify every category "
    "over budget, compute the total overrun, then propose a set of cuts to "
    "under-budget categories that fully offsets the overrun WITHOUT cutting any "
    "category below its actual spend. Report the proposed cuts and verify the "
    "offset balances to zero."
)
# 70ff3369 — deepseek-v4-pro. Verifies the offset ("fully offset", "no category cut
# below its actual spend") — phrased differently from "balances to zero".
BUDGET_ANSWER = (
    "FINAL ANSWER:\n\n**Budget Analysis and Cut Proposal**\n\n**Data:**\n\n"
    "| Category | Planned | Actual | Status |\n"
    "| food     | 100     | 130    | Over by 30 |\n"
    "| travel   | 200     | 150    | Under by 50 |\n"
    "| office   | 80      | 60     | Under by 20 |\n"
    "| rent     | 500     | 500    | On budget |\n\n"
    "**Overrun:** Only `food` is over budget, by **30**.\n\n"
    "**Proposed Cut:** Reduce the **travel** category's planned budget from "
    "**200 to 170** (a cut of **30**). This fully offsets the 30 overrun from food, "
    "and travel's new planned amount (170) remains safely above its actual spend "
    "(150).\n\n"
    "The overrun is fully offset with no category cut below its actual spend."
)
# budget.csv source data (identical bytes to the seeder fixture).
BUDGET_EVIDENCE = [
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/budget.csv", "operation": "read"},
        "tool_output": (
            "category,planned,actual\n"
            "food,100,130\ntravel,200,150\noffice,80,60\nrent,500,500\n"
        ),
    }
]

CITATION_TASK = (
    "Read /workspace/papers/ (paper-1.txt … paper-4.txt). Each paper cites others "
    "by their number in a 'cites:' line. Build the citation graph, find the paper "
    "cited by the most others, then summarise THAT paper's key claim and explain "
    "which papers depend on it and why. Read every paper before answering."
)
# df252d51 — claude-haiku-4-5. Names Paper 3 (the hub) + topology + reading order,
# but states only its TITLE ("Foundations of locality"), never its CLAIM.
CITATION_ANSWER = (
    "## FINAL ANSWER:\n\n**Citation Graph Analysis Complete**\n\n"
    "### Papers Overview:\n"
    "- **Paper 1**: Caching strategies (cites Paper 3)\n"
    "- **Paper 2**: Index tuning (cites Paper 3)\n"
    "- **Paper 3**: Foundations of locality (no citations - foundational)\n"
    "- **Paper 4**: Prefetching (cites Paper 3)\n\n"
    "### Dependency Structure:\n"
    "The citation graph forms a **star topology** with Paper 3 at the center:\n"
    "- Paper 3 is foundational with no dependencies\n"
    "- Papers 1, 2, and 4 all depend on Paper 3\n\n"
    "### Recommended Reading Order:\n"
    "1. Read Paper 3 first (Foundations of locality)\n"
    "2. Read Papers 1, 2, and 4 in any order"
)
# paper-3.txt carries the CLAIM the answer omitted (identical bytes to the seeder).
CITATION_EVIDENCE = [
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-1.txt"},
        "tool_output": "Title: Caching strategies.\nClaim: LRU beats FIFO under skew.\ncites: 3\n",
    },
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-2.txt"},
        "tool_output": "Title: Index tuning.\nClaim: Covering indexes cut IO.\ncites: 3\n",
    },
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-3.txt"},
        "tool_output": "Title: Foundations of locality.\nClaim: Temporal locality dominates real workloads.\ncites: \n",
    },
    {
        "tool_name": "file_io",
        "tool_input": {"path": "/workspace/papers/paper-4.txt"},
        "tool_output": "Title: Prefetching.\nClaim: Prefetch depth 2 is optimal.\ncites: 3\n",
    },
]

# Canned verdict — the rendered prompt is what we assert on; the verdict is inert.
_CANNED = (
    '{"goal_met": true, "criteria_met": 1.0, "per_criterion": [], '
    '"rationale": "canned", "graceful_failure": false}'
)


def _judge() -> tuple[GoalJudge, FakeLLMService]:
    llm = FakeLLMService(_CANNED)
    judge = GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    return judge, llm


async def _rendered_prompt(task: str, answer: str, evidence: list[dict]) -> str:
    """Drive evaluate() and return the prompt string sent to the (fake) model."""
    judge, llm = _judge()
    await judge.evaluate(
        task_input=task,
        final_answer=answer,
        success_conditions=[],
        evidence=evidence,
    )
    # FakeLLMService records (profile, messages); the rubric is the single message.
    assert llm.calls, "judge did not call the LLM — verifier short-circuited"
    _profile_arg, messages = llm.calls[-1]
    return messages[-1]["content"]


# ─────────────────────────────────────────────────────────────────────
# Both residual-fp cases must reach the LLM fallback (the verifier abstains),
# so the prompt — not a deterministic verifier — is what judges them.
# ─────────────────────────────────────────────────────────────────────


class TestBothCasesRouteToLLMFallback:
    def test_budget_offset_verifier_abstains(self):
        # The budget-offset task is too compound to parse from prose — keep it
        # abstaining (mirrors test_budget_offset_abstains). The prompt owns it.
        assert verify_answer(BUDGET_TASK, BUDGET_ANSWER, BUDGET_EVIDENCE) is None

    def test_citation_verifier_abstains(self):
        assert verify_answer(CITATION_TASK, CITATION_ANSWER, CITATION_EVIDENCE) is None

    @pytest.mark.asyncio
    async def test_budget_evaluate_consults_the_llm(self):
        judge, llm = _judge()
        await judge.evaluate(
            task_input=BUDGET_TASK,
            final_answer=BUDGET_ANSWER,
            success_conditions=[],
            evidence=BUDGET_EVIDENCE,
        )
        assert llm.calls, "budget-offset must fall through to the LLM judge"

    @pytest.mark.asyncio
    async def test_citation_evaluate_consults_the_llm(self):
        judge, llm = _judge()
        await judge.evaluate(
            task_input=CITATION_TASK,
            final_answer=CITATION_ANSWER,
            success_conditions=[],
            evidence=CITATION_EVIDENCE,
        )
        assert llm.calls, "citation-synthesis must fall through to the LLM judge"


# ─────────────────────────────────────────────────────────────────────
# THE FIX: the rendered fallback prompt carries the semantic-satisfaction clause.
# ─────────────────────────────────────────────────────────────────────

# Stable literal substrings of the new clause in goal_judge_system_prompt.j2.
# Keep each a contiguous literal — the prose may wrap between them.
_SEMANTIC_CLAUSE_MARKERS = (
    "SEMANTIC-SATISFACTION",
    "outcome",
    "without echoing",
)


class TestSemanticSatisfactionClausePresent:
    @pytest.mark.asyncio
    async def test_clause_renders_for_budget_case(self):
        prompt = await _rendered_prompt(BUDGET_TASK, BUDGET_ANSWER, BUDGET_EVIDENCE)
        missing = [m for m in _SEMANTIC_CLAUSE_MARKERS if m not in prompt]
        assert not missing, f"semantic-satisfaction clause markers missing: {missing}"

    @pytest.mark.asyncio
    async def test_clause_is_evidence_gated(self):
        # The clause must tie satisfaction to corroborating evidence/data, not bare
        # narration — otherwise it would loosen the corrupt-success check.
        prompt = await _rendered_prompt(BUDGET_TASK, BUDGET_ANSWER, BUDGET_EVIDENCE)
        assert "corroborat" in prompt or "supporting evidence" in prompt, (
            "semantic-satisfaction clause must be evidence-gated, not bare-claim"
        )


# ─────────────────────────────────────────────────────────────────────
# GUARDS: the softening must NOT remove the corrupt-success / evidence-grounding
# rubric (the topo + fabrication families depend on it), and the citation case
# must still face the strict "claim, not title" rubric.
# ─────────────────────────────────────────────────────────────────────


class TestSofteningKeepsTheGuards:
    @pytest.mark.asyncio
    async def test_corrupt_success_markers_survive(self):
        prompt = await _rendered_prompt(BUDGET_TASK, BUDGET_ANSWER, BUDGET_EVIDENCE)
        for marker in ("CORRUPT-SUCCESS", "partial_fraction", "claims done"):
            assert marker in prompt, (
                f"softening dropped corrupt-success marker {marker!r}"
            )

    @pytest.mark.asyncio
    async def test_evidence_grounding_markers_survive(self):
        prompt = await _rendered_prompt(BUDGET_TASK, BUDGET_ANSWER, BUDGET_EVIDENCE)
        for marker in (
            "EVIDENCE-GROUNDING",
            "Treat the agent's own",
            "narration of progress",
        ):
            assert marker in prompt, (
                f"softening dropped evidence-grounding marker {marker!r}"
            )

    @pytest.mark.asyncio
    async def test_citation_evidence_exposes_the_unstated_claim(self):
        # The digest carries paper-3's CLAIM, so the judge has what it needs to see
        # the answer omitted it. (The answer states the title, not this claim.)
        digest = _summarize_evidence(CITATION_EVIDENCE)
        assert "Temporal locality dominates real workloads" in digest
        assert "Temporal locality dominates real workloads" not in CITATION_ANSWER
