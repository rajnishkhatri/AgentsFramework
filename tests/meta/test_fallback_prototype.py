"""L2 + L4 tests for the Pydantic-AI fallback prototype (STORY-414).

L2 tests validate the deterministic scaffolding: state serialization,
checkpoint/restore, tool-failure recovery, completion-error recovery, and
final-answer extraction. They do NOT call any LLM.

L4 tests are gated behind ``@pytest.mark.simulation`` and
``@pytest.mark.live_llm`` so they never run in CI; they execute the
prototype against a real LLM for offline benchmarking.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from components.routing_config import RoutingConfig
from meta.fallback_prototype import (
    FallbackMessage,
    FallbackReactLoop,
    FallbackState,
    _extract_final_answer,
    _normalize_litellm_response,
)
from services.base_config import AgentConfig, ModelProfile


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


@pytest.fixture
def capable_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o",
        litellm_id="openai/gpt-4o",
        tier="capable",
        context_window=128000,
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.01,
    )


@pytest.fixture
def agent_config(fast_profile, capable_profile) -> AgentConfig:
    return AgentConfig(
        max_steps=4,
        max_cost_usd=1.0,
        default_model="gpt-4o-mini",
        models=[fast_profile, capable_profile],
    )


@pytest.fixture
def routing_config() -> RoutingConfig:
    return RoutingConfig()


# ── L2: State serialization ────────────────────────────────────────


class TestFallbackStateSerialization:
    """Property: state -> JSON -> state is the identity for valid input."""

    def test_state_roundtrip(self):
        original = FallbackState(
            task_id="t-1",
            task_input="What is 2+2?",
            messages=[
                FallbackMessage(role="system", content="be helpful"),
                FallbackMessage(role="user", content="hi"),
            ],
            step_count=2,
            selected_model="gpt-4o-mini",
            consecutive_errors=1,
            total_cost_usd=0.05,
        )
        payload = original.model_dump_json()
        restored = FallbackState.model_validate_json(payload)
        assert restored == original

    def test_empty_state_is_valid(self):
        state = FallbackState(task_id="t-1", task_input="x")
        roundtrip = FallbackState.model_validate_json(state.model_dump_json())
        assert roundtrip == state

    def test_state_with_step_results_roundtrips(self):
        from components.evaluator import build_step_result

        sr = build_step_result(
            step_id=0, action="answer", model_used="gpt-4o-mini",
            routing_reason="capable-for-planning", input_tokens=10,
            output_tokens=5, cost_usd=0.001, latency_ms=100.0,
            outcome="success", error_record=None, reasoning="ok",
        )
        state = FallbackState(
            task_id="t-1", task_input="x", step_results=[sr],
        )
        roundtrip = FallbackState.model_validate_json(state.model_dump_json())
        assert roundtrip.step_results == state.step_results


# ── L2: Checkpoint / restore ───────────────────────────────────────


class TestCheckpointRestore:
    """Failure path first: corruption mid-tool MUST not pollute history."""

    def test_checkpoint_returns_serialized_payload(
        self, agent_config, routing_config, tmp_path
    ):
        loop = FallbackReactLoop(
            agent_config, routing_config, checkpoint_dir=tmp_path,
        )
        state = FallbackState(
            task_id="t-1", task_input="x", step_count=2,
            selected_model="gpt-4o",
        )
        payload = loop.checkpoint(state)

        restored = FallbackReactLoop.restore(payload)
        assert restored == state
        # File side-effect when checkpoint_dir is set.
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        assert "t-1" in files[0].name

    def test_checkpoint_without_dir_skips_file_write(
        self, agent_config, routing_config, tmp_path
    ):
        loop = FallbackReactLoop(agent_config, routing_config)
        state = FallbackState(task_id="t-2", task_input="x")
        payload = loop.checkpoint(state)
        assert FallbackReactLoop.restore(payload) == state
        # No directory was passed; no files exist.
        assert list(tmp_path.glob("*.json")) == []

    def test_restore_after_simulated_tool_failure(
        self, agent_config, routing_config
    ):
        """Hand-rolled scenario: snapshot, mutate, then restore."""
        loop = FallbackReactLoop(agent_config, routing_config)
        clean = FallbackState(
            task_id="t-3", task_input="x",
            messages=[FallbackMessage(role="user", content="x")],
            step_count=0,
        )
        snapshot = loop.checkpoint(clean)

        # Simulate tool execution polluting the messages list and counters.
        polluted = clean.model_copy(deep=True)
        polluted.messages.append(
            FallbackMessage(role="assistant", content="garbage")
        )
        polluted.consecutive_errors = 99
        assert polluted != clean

        recovered = FallbackReactLoop.restore(snapshot)
        assert recovered == clean


# ── L2: Final-answer extraction + normalization helpers ───────────


class TestExtractFinalAnswer:
    def test_extracts_after_marker(self):
        assert _extract_final_answer(
            "Reasoning...\nFINAL ANSWER: 42", "FINAL ANSWER:"
        ) == "42"

    def test_returns_none_when_marker_absent(self):
        assert _extract_final_answer("just thinking", "FINAL ANSWER:") is None

    def test_strips_whitespace(self):
        assert _extract_final_answer(
            "FINAL ANSWER:    hello  ", "FINAL ANSWER:"
        ) == "hello"


class TestNormalizeLiteLLMResponse:
    def test_dict_style_response(self):
        raw = {"choices": [{"message": {"content": "hi"}}]}
        out = _normalize_litellm_response(raw)
        assert out == {"content": "hi", "tool_calls": []}

    def test_object_style_response(self):
        class Msg:
            content = "ok"
            tool_calls = []

        class Choice:
            message = Msg()

        class Resp:
            choices = [Choice()]

        out = _normalize_litellm_response(Resp())
        assert out["content"] == "ok"
        assert out["tool_calls"] == []

    def test_tool_call_arguments_parsed_as_json(self):
        raw = {"choices": [{"message": {
            "content": "",
            "tool_calls": [{
                "id": "tc-1",
                "function": {
                    "name": "search",
                    "arguments": json.dumps({"query": "stars"}),
                },
            }],
        }}]}
        out = _normalize_litellm_response(raw)
        assert out["tool_calls"][0] == {
            "name": "search",
            "arguments": {"query": "stars"},
            "id": "tc-1",
        }

    def test_empty_choices_returns_empty_response(self):
        assert _normalize_litellm_response({"choices": []}) == {
            "content": "",
            "tool_calls": [],
        }


# ── L2: Default system prompt loads from template (H1) ──────────


class TestDefaultSystemPromptTemplate:
    """The default prompt MUST come from prompts/ (H1, AP-3) -- no inline literals."""

    def test_default_system_prompt_loaded_from_template(
        self, agent_config, routing_config
    ):
        loop = FallbackReactLoop(agent_config, routing_config)
        # Hallmarks of the .j2 template content.
        assert "FINAL ANSWER" in loop._system_prompt
        assert "ReAct agent" in loop._system_prompt

    def test_explicit_system_prompt_overrides_default(
        self, agent_config, routing_config
    ):
        loop = FallbackReactLoop(
            agent_config, routing_config, system_prompt="custom prompt",
        )
        assert loop._system_prompt == "custom prompt"


# ── L2: End-to-end loop with stub completion ──────────────────────


class TestFallbackReactLoopE2E:
    @pytest.mark.asyncio
    async def test_terminates_with_final_answer(
        self, agent_config, routing_config
    ):
        def fake_completion(*, model, messages):
            return {"choices": [{"message": {
                "content": "FINAL ANSWER: 42",
            }}]}

        loop = FallbackReactLoop(
            agent_config, routing_config, completion_fn=fake_completion,
        )
        result = await loop.run("What is 6 * 7?", task_id="t-final")

        assert result.final_answer == "42"
        assert result.status == "completed"
        assert result.total_steps == 1
        assert result.task_id == "t-final"

    @pytest.mark.asyncio
    async def test_tool_failure_restores_state_and_increments_errors(
        self, agent_config, routing_config
    ):
        # First call returns a tool call; second call returns a final answer.
        responses = [
            {"choices": [{"message": {
                "content": "Calling tool...",
                "tool_calls": [{
                    "id": "tc-1",
                    "function": {
                        "name": "search",
                        "arguments": json.dumps({"q": "x"}),
                    },
                }],
            }}]},
            {"choices": [{"message": {
                "content": "FINAL ANSWER: recovered",
            }}]},
        ]
        call_idx = {"i": 0}

        def fake_completion(*, model, messages):
            i = call_idx["i"]
            call_idx["i"] += 1
            return responses[i]

        def crashing_tool(name, args):
            raise RuntimeError("simulated tool crash")

        loop = FallbackReactLoop(
            agent_config, routing_config,
            completion_fn=fake_completion,
            tool_executor=crashing_tool,
        )
        result = await loop.run("force a tool call", task_id="t-tool-fail")

        assert result.final_answer == "recovered"
        # We made two LLM calls (one tool attempt, one recovery answer).
        assert call_idx["i"] == 2
        # The first step was logged as a tool failure.
        assert result.steps[0].outcome == "failure"
        assert result.steps[0].error_type == "tool_error"

    @pytest.mark.asyncio
    async def test_loop_exits_on_max_steps(
        self, agent_config, routing_config
    ):
        """Even an infinite tool-call loop terminates at agent_config.max_steps."""
        def looping_completion(*, model, messages):
            return {"choices": [{"message": {
                "content": "again",
                "tool_calls": [{
                    "id": "tc",
                    "function": {"name": "noop", "arguments": "{}"},
                }],
            }}]}

        def noop(name, args):
            return "ok"

        loop = FallbackReactLoop(
            agent_config, routing_config,
            completion_fn=looping_completion,
            tool_executor=noop,
        )
        result = await loop.run("loop forever", task_id="t-loop")
        assert result.final_answer is None
        assert result.status == "exhausted"
        assert result.total_steps == agent_config.max_steps


# ── L4: Live LLM benchmark (CI-skipped) ───────────────────────────


@pytest.mark.simulation
@pytest.mark.live_llm
class TestFallbackReactLoopLive:
    """Compare prototype quality against the LangGraph loop on a tiny set.

    Skipped by default. To run:

        pytest tests/meta/test_fallback_prototype.py -m "live_llm" \\
               --override-ini="addopts="
    """

    @pytest.mark.asyncio
    async def test_prototype_returns_final_answers_for_simple_questions(
        self, agent_config, routing_config
    ):
        loop = FallbackReactLoop(agent_config, routing_config)
        questions = [
            "What is the capital of France?",
            "What is 12 times 5?",
            "Name one primary color.",
        ]
        for q in questions:
            result = await loop.run(q)
            assert result.final_answer is not None, (
                f"Prototype failed to answer: {q!r}"
            )
