"""F10 Tier-2 reasoning recap node (eval-UI plan §8 F10 / §8.6-B).

L2 with a mocked LLM provider — the recap is one cheap-tier completion per
run; CI never calls a live model. Failure paths first (TAP-4): the cost
guard, the empty-response path, and the never-break-the-run exception
guard are asserted before the happy path.
"""

from __future__ import annotations

from typing import Any

import pytest

from orchestration.react_loop import _reasoning_recap_impl
from services.base_config import AgentConfig, ModelProfile
from services.prompt_service import PromptService


class _FakeLLMService:
    def __init__(
        self, content: str = "Recap text.", error: Exception | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._content = content
        self._error = error

    async def invoke(
        self, profile: ModelProfile, messages: list[dict], **kwargs: Any
    ) -> Any:
        self.calls.append({"profile": profile, "messages": messages, "kwargs": kwargs})
        if self._error is not None:
            raise self._error
        return type("Resp", (), {"content": self._content})()


def _profile(name: str, tier: str) -> ModelProfile:
    return ModelProfile(
        name=name,
        litellm_id=f"openai/{name}",
        tier=tier,
        context_window=128000,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.002,
    )


def _config(models: list[ModelProfile] | None = None) -> AgentConfig:
    models = models if models is not None else [_profile("gpt-4o-mini", "fast")]
    return AgentConfig(models=models, default_model=models[0].name)


def _tool_record(tool_name: str = "file_io", ok: bool = True, **over: Any) -> dict:
    rec = {
        "record_id": f"1:{tool_name}",
        "step_id": 1,
        "tool_name": tool_name,
        "tool_input": {"path": "/workspace/x.txt"},
        "tool_output": "ok",
        "ok": ok,
        "error": None if ok else "boom",
    }
    rec.update(over)
    return rec


def _state(tool_count: int = 2, task: str = "do the thing") -> dict:
    return {
        "task_input": task,
        "tool_results": [
            _tool_record(f"tool_{i}", record_id=f"1:call-{i}")
            for i in range(tool_count)
        ],
        "messages": [
            type("Msg", (), {"content": "Final answer prose.", "tool_calls": []})()
        ],
    }


@pytest.mark.asyncio
class TestReasoningRecapCostGuard:
    async def test_zero_tool_run_is_skipped(self) -> None:
        llm = _FakeLLMService()
        out = await _reasoning_recap_impl(
            _state(tool_count=0),
            llm_service=llm,
            prompt_service=PromptService(),
            agent_config=_config(),
        )
        assert out == {}
        assert llm.calls == []

    async def test_single_tool_run_is_skipped(self) -> None:
        llm = _FakeLLMService()
        out = await _reasoning_recap_impl(
            _state(tool_count=1),
            llm_service=llm,
            prompt_service=PromptService(),
            agent_config=_config(),
        )
        assert out == {}
        assert llm.calls == []


@pytest.mark.asyncio
class TestReasoningRecapFailureModes:
    async def test_llm_exception_never_breaks_the_run(self) -> None:
        llm = _FakeLLMService(error=RuntimeError("provider down"))
        out = await _reasoning_recap_impl(
            _state(),
            llm_service=llm,
            prompt_service=PromptService(),
            agent_config=_config(),
        )
        assert out == {}

    async def test_empty_completion_emits_nothing(self) -> None:
        llm = _FakeLLMService(content="   ")
        out = await _reasoning_recap_impl(
            _state(),
            llm_service=llm,
            prompt_service=PromptService(),
            agent_config=_config(),
        )
        assert out == {}


@pytest.mark.asyncio
class TestReasoningRecapHappyPath:
    async def test_returns_reasoning_summary_from_cheap_tier(self) -> None:
        fast = _profile("gpt-4o-mini", "fast")
        big = _profile("gpt-4o", "balanced")
        llm = _FakeLLMService(content="Did A then B because C.")
        out = await _reasoning_recap_impl(
            _state(),
            llm_service=llm,
            prompt_service=PromptService(),
            agent_config=_config([big, fast]),
        )
        assert out == {"reasoning_summary": "Did A then B because C."}
        assert len(llm.calls) == 1, "exactly one completion per run"
        assert llm.calls[0]["profile"] is fast, "must pick the fast tier, not models[0]"

    async def test_call_is_tagged_so_runtime_can_suppress_token_leak(self) -> None:
        llm = _FakeLLMService()
        await _reasoning_recap_impl(
            _state(),
            llm_service=llm,
            prompt_service=PromptService(),
            agent_config=_config(),
        )
        config = llm.calls[0]["kwargs"].get("config") or {}
        assert "reasoning_recap" in (config.get("tags") or [])

    async def test_prompt_carries_task_tools_and_answer(self) -> None:
        llm = _FakeLLMService()
        await _reasoning_recap_impl(
            _state(task="rename the file"),
            llm_service=llm,
            prompt_service=PromptService(),
            agent_config=_config(),
        )
        prompt = llm.calls[0]["messages"][0]["content"]
        assert "rename the file" in prompt
        assert "tool_0" in prompt and "tool_1" in prompt
        assert "Final answer prose." in prompt


class TestReasoningRecapTemplate:
    def test_template_renders_under_strict_undefined(self) -> None:
        """F-R5: the prompt is a Jinja template in prompts/, tested for render."""
        rendered = PromptService().render_prompt(
            "reasoning_recap",
            task_input="t",
            tool_steps=[
                {
                    "tool_name": "file_io",
                    "tool_input": {"p": 1},
                    "ok": True,
                    "error": None,
                },
                {
                    "tool_name": "web_search",
                    "tool_input": {},
                    "ok": False,
                    "error": "x",
                },
            ],
            final_answer="a",
        )
        assert "file_io" in rendered
        assert "FAILED: x" in rendered
