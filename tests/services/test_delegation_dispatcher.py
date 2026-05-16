"""L2 contract tests for LocalLLMDelegationDispatcher."""

from __future__ import annotations

from services.base_config import AgentConfig, ModelProfile
from services.tools.delegation_dispatcher import LocalLLMDelegationDispatcher


def _fast_profile() -> ModelProfile:
    return ModelProfile(
        name="gpt-4o-mini",
        litellm_id="openai/gpt-4o-mini",
        tier="fast",
        context_window=128000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    )


class _FakeResponse:
    def __init__(self) -> None:
        self.content = '{"result":"ok"}'
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 5}


def test_dispatch_returns_completed_payload(monkeypatch):
    dispatcher = LocalLLMDelegationDispatcher(
        AgentConfig(default_model="gpt-4o-mini", models=[_fast_profile()])
    )
    fake_response = _FakeResponse()

    calls = {"count": 0}

    def _fake_run_async(_coro):  # noqa: ANN001
        close = getattr(_coro, "close", None)
        if callable(close):
            close()
        calls["count"] += 1
        if calls["count"] == 1:
            return fake_response
        return None

    monkeypatch.setattr(dispatcher, "_run_async", _fake_run_async)

    result = dispatcher.dispatch({
        "correlation_id": "wf-1:step:2:research",
        "workflow_id": "wf-1",
        "step_count": 2,
        "objective": "Summarize current blockers",
        "subagent_type": "research",
        "constraints": ["No external URLs"],
        "expected_output_schema": {"type": "object"},
        "task_id": "task-1",
        "user_id": "user-1",
    })
    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["output"] == fake_response.content
    assert result["child_correlation_id"].startswith("wf-1:step:2:research:child:")
