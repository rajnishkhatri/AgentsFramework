"""L2 contract tests for LocalLLMDelegationDispatcher (sync + async)."""

from __future__ import annotations

import asyncio

import pytest

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


def _dispatcher() -> LocalLLMDelegationDispatcher:
    return LocalLLMDelegationDispatcher(
        AgentConfig(default_model="gpt-4o-mini", models=[_fast_profile()])
    )


def _stub_worker(dispatcher, monkeypatch, *, response=None, raises=None):
    """Patch the LLM seam (_invoke_worker) and silence eval capture.

    Both sync dispatch and async dispatch_async share _dispatch_core, so
    stubbing the worker exercises the same code path for both — the contract
    test that the two return the SAME shape (P6, no live LLM, AP5).
    """

    async def _fake_invoke(_validated):  # noqa: ANN001
        if raises is not None:
            raise raises
        return response

    async def _fake_capture(**_kwargs):  # noqa: ANN003
        return None

    monkeypatch.setattr(dispatcher, "_invoke_worker", _fake_invoke)
    monkeypatch.setattr(dispatcher, "_record_eval_capture", _fake_capture)


_REQUEST = {
    "correlation_id": "wf-1:step:2:research",
    "workflow_id": "wf-1",
    "step_count": 2,
    "objective": "Summarize current blockers",
    "subagent_type": "research",
    "constraints": ["No external URLs"],
    "expected_output_schema": {"type": "object"},
    "task_id": "task-1",
    "user_id": "user-1",
}


# ── sync path (the existing non-graph caller) ───────────────────────────────


def test_sync_dispatch_returns_completed_payload(monkeypatch):
    dispatcher = _dispatcher()
    resp = _FakeResponse()
    _stub_worker(dispatcher, monkeypatch, response=resp)

    result = dispatcher.dispatch(_REQUEST)

    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["output"] == resp.content
    assert result["child_correlation_id"].startswith("wf-1:step:2:research:child:")


# ── async path (the T3 worker node, Step 5b) ────────────────────────────────


def test_async_dispatch_matches_sync_shape(monkeypatch):
    """dispatch_async returns the SAME {status, output, error,
    child_correlation_id} shape as sync dispatch (Protocol B contract)."""
    dispatcher = _dispatcher()
    resp = _FakeResponse()
    _stub_worker(dispatcher, monkeypatch, response=resp)

    result = asyncio.run(dispatcher.dispatch_async(_REQUEST))

    assert set(result) == {"status", "output", "error", "child_correlation_id"}
    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["output"] == resp.content
    assert result["child_correlation_id"].startswith("wf-1:step:2:research:child:")


def test_async_dispatch_propagates_llm_exception(monkeypatch):
    """An LLM exception PROPAGATES from dispatch_async — it is NOT swallowed.

    The worker node (not the dispatcher) owns the failure sentinel; the
    dispatcher's job is to surface the error so the node's try/except can record
    a per-branch sentinel (plan §2 Step 5b / Step 6)."""
    dispatcher = _dispatcher()
    _stub_worker(dispatcher, monkeypatch, raises=RuntimeError("model boom"))

    with pytest.raises(RuntimeError, match="model boom"):
        asyncio.run(dispatcher.dispatch_async(_REQUEST))
