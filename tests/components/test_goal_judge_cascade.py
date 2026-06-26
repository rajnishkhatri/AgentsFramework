"""L3 (mock-provider) tests for the GoalJudge correctness cascade.

The cascade puts a deterministic ``verify_answer`` check in front of the LLM
rubric for tasks with a checkable answer. These tests pin the cascade contract
with a mocked LLM (never a live model, TAP-5):

  - verifier returns False → ``goal_met=False`` REGARDLESS of what the model
    says (kills the missed-failure: a reversed topo sort the LLM rated 1.0);
  - verifier returns True  → ``goal_met=True`` REGARDLESS of the model (kills
    the false-downgrade: a correct order the LLM failed for not echoing);
  - verifier returns None  → the LLM verdict is used UNCHANGED (full back-compat
    for non-checkable tasks and the items the judge already gets right).

Failure path first (TAP-4/TAP-6): the two authoritative-override cases (which
flip the model) come before the pass-through case. We assert the verdict shape
and the ``verifier_source`` provenance, never model prose (TAP-3).
"""

from __future__ import annotations

import json

import pytest

from components.goal_judge import GoalJudge
from components.schemas import GoalVerdict
from services.base_config import ModelProfile
from services.prompt_service import PromptService

TOPO_TASK = (
    "Read /workspace/deps.txt where each line is 'A -> B' meaning A depends on "
    "B. Produce a valid install order (a topological sort) such that every "
    "dependency is installed before the thing that needs it, and report the order."
)
DEPS_EVIDENCE = [
    {
        "tool_name": "read_file",
        "tool_input": {"path": "/workspace/deps.txt"},
        "tool_output": "A -> B\nA -> C\nB -> D\nC -> D\n",
    }
]


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLMService:
    """In-memory LLM stub: replays a canned verdict, records whether it was called."""

    def __init__(self, verdict: dict) -> None:
        self._content = json.dumps(verdict)
        self.calls: list = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        return _FakeResponse(self._content)


def _profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


def _judge(llm_verdict: dict) -> tuple[GoalJudge, FakeLLMService]:
    llm = FakeLLMService(llm_verdict)
    judge = GoalJudge(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        judge_profile=_profile(),
    )
    return judge, llm


# A verdict shape the LLM might return (mirrors the production rubric output).
_LLM_SAYS_MET = {"goal_met": True, "criteria_met": 1.0, "rationale": "looks done"}
_LLM_SAYS_NOT = {"goal_met": False, "criteria_met": 0.6, "rationale": "not echoed"}


# ── verifier is authoritative (failure path first) ──────────────────


@pytest.mark.asyncio
async def test_reversed_order_fails_even_when_llm_says_met():
    """The missed-failure: model rated the reversed sort met; verifier overrides."""
    judge, llm = _judge(_LLM_SAYS_MET)
    verdict = await judge.evaluate(
        task_input=TOPO_TASK,
        final_answer="Install order: A, B, C, D",
        success_conditions=[],
        evidence=DEPS_EVIDENCE,
    )
    assert verdict.goal_met is False
    assert verdict.verifier_source == "deterministic"
    assert llm.calls == [], "verifier was authoritative — the LLM must NOT be called"


@pytest.mark.asyncio
async def test_correct_order_passes_even_when_llm_says_not_met():
    """The false-downgrade: model failed a correct order for formatting; verifier overrides."""
    judge, llm = _judge(_LLM_SAYS_NOT)
    verdict = await judge.evaluate(
        task_input=TOPO_TASK,
        final_answer="The install order is: D, B, C, A",
        success_conditions=[],
        evidence=DEPS_EVIDENCE,
    )
    assert verdict.goal_met is True
    assert verdict.verifier_source == "deterministic"
    assert llm.calls == []


# ── verifier abstains → LLM verdict used unchanged (back-compat) ─────


@pytest.mark.asyncio
async def test_non_checkable_task_uses_llm_verdict():
    judge, llm = _judge(_LLM_SAYS_MET)
    verdict = await judge.evaluate(
        task_input="Summarise the attached paper's key claim in two sentences.",
        final_answer="The paper argues X causes Y.",
        success_conditions=[],
        evidence=None,
    )
    assert verdict.goal_met is True
    assert verdict.verifier_source is None
    assert len(llm.calls) == 1, "no checkable shape — the LLM judge must run"


@pytest.mark.asyncio
async def test_unparseable_checkable_answer_defers_to_llm():
    judge, llm = _judge(_LLM_SAYS_NOT)
    verdict = await judge.evaluate(
        task_input=TOPO_TASK,
        final_answer="I read the file and computed a sort.",  # no order tokens
        success_conditions=[],
        evidence=DEPS_EVIDENCE,
    )
    assert verdict.goal_met is False  # the LLM's verdict, untouched
    assert verdict.verifier_source is None
    assert len(llm.calls) == 1
