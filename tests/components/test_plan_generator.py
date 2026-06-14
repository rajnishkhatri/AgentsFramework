"""L1/Protocol-C tests for components/plan_generator.py (mocked LLM).

Failure-first (AP6): the raise/parse-failure paths land before the happy path.
The generator's contract is narrow — render, invoke, return the decoded dict OR
raise — so most behavior (parse/validate/floor) is asserted in
``test_plan_builder.py`` against ``build_plan_artifact_llm``. These tests pin the
LLM boundary: prompt is rendered, response is decoded, errors propagate.
"""

from __future__ import annotations

import json

import pytest

from components.plan_generator import PlanGenerator
from services.base_config import ModelProfile
from services.prompt_service import PromptService


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLMService:
    """In-memory LLM stub: replays a canned response, records each call."""

    def __init__(self, content: str, *, raises: Exception | None = None) -> None:
        self._content = content
        self._raises = raises
        self.calls: list[tuple[ModelProfile, list[dict]]] = []

    async def invoke(self, profile, messages, **kwargs):
        self.calls.append((profile, messages))
        if self._raises is not None:
            raise self._raises
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


def _generator(content: str, *, raises: Exception | None = None):
    llm = FakeLLMService(content, raises=raises)
    gen = PlanGenerator(
        llm_service=llm,  # type: ignore[arg-type]
        prompt_service=PromptService(),
        profile=_profile(),
    )
    return gen, llm


_PLAN_JSON = json.dumps(
    {
        "ordered_steps": [
            {"title": "Survey", "goal": "survey the schema"},
            {"title": "Migrate", "goal": "apply the migration"},
        ],
        "constraints": ["no downtime"],
        "success_conditions": ["migration is applied"],
    }
)


# ── failure paths first (AP6) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_propagates_llm_transport_error() -> None:
    """LLM raises -> generate raises (the node owns the floor fallback)."""
    gen, _ = _generator("", raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await gen.generate(task_input="Plan it.", planning_depth="L1")


@pytest.mark.asyncio
async def test_generate_raises_on_malformed_json() -> None:
    gen, _ = _generator("this is not json at all")
    with pytest.raises(Exception):
        await gen.generate(task_input="Plan it.", planning_depth="L1")


@pytest.mark.asyncio
async def test_generate_raises_when_response_is_a_json_array() -> None:
    gen, _ = _generator("[1, 2, 3]")
    with pytest.raises(ValueError):
        await gen.generate(task_input="Plan it.", planning_depth="L1")


# ── happy path ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_returns_decoded_dict() -> None:
    gen, llm = _generator(_PLAN_JSON)
    data = await gen.generate(task_input="Plan the migration.", planning_depth="L2")
    assert isinstance(data, dict)
    assert len(data["ordered_steps"]) == 2
    # The fast-tier profile and a single rendered message were used.
    assert len(llm.calls) == 1
    profile, messages = llm.calls[0]
    assert profile.tier == "fast"
    assert messages[0]["role"] == "user"
    # The task text reached the prompt (no exact-prompt assertion — AP3).
    assert "Plan the migration." in messages[0]["content"]


@pytest.mark.asyncio
async def test_generate_extracts_json_from_fenced_response() -> None:
    gen, _ = _generator(f"Here is the plan:\n```json\n{_PLAN_JSON}\n```\nDone.")
    data = await gen.generate(task_input="Plan it.", planning_depth="L1")
    assert len(data["ordered_steps"]) == 2
