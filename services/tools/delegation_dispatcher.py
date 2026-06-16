"""Dispatcher for live local sub-agent delegation runs.

Provides a framework-agnostic callback used by ``task_tool`` to run delegated
work in an isolated worker invocation and return a normalized handoff payload.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from services.base_config import AgentConfig, default_fast_profile
from services.llm_config import LLMService
from services.prompt_service import PromptService


class DelegationDispatchRequest(BaseModel):
    correlation_id: str
    workflow_id: str = ""
    step_count: int = 0
    objective: str = Field(min_length=1, max_length=400)
    subagent_type: str = Field(min_length=1, max_length=80)
    constraints: list[str] = Field(default_factory=list)
    expected_output_schema: dict[str, Any] = Field(default_factory=dict)
    task_id: str = ""
    user_id: str = "anonymous"


@dataclass
class _ThreadResult:
    value: Any | None = None
    error: BaseException | None = None


class LocalLLMDelegationDispatcher:
    """Concrete delegation callback using the configured local LLM stack."""

    def __init__(self, agent_config: AgentConfig, *, worker_model: str | None = None) -> None:
        self._agent_config = agent_config
        self._llm_service = LLMService(agent_config)
        self._prompt_service = PromptService()
        self._worker_model_name = worker_model or agent_config.default_model

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        """Synchronous delegation for non-graph callers (``task_tool``).

        Runs the async core on a private event loop via the thread shim, since
        ``task_tool.execute_task_tool`` is a sync, non-graph caller. The T3
        worker node uses :meth:`dispatch_async` instead (it is already inside
        the graph's loop — no shim needed).
        """
        return self._run_async(self._dispatch_core(DelegationDispatchRequest(**request)))

    async def dispatch_async(self, request: dict[str, Any]) -> dict[str, Any]:
        """Async delegation for the T3 worker node (inside the graph loop).

        Awaits the worker directly — no ``_run_async`` thread shim. The worker
        node owns the failure sentinel: an LLM exception PROPAGATES from here
        (it is not swallowed), and the node's mandatory ``try/except`` converts
        it to a per-branch sentinel so one branch never cancels the superstep
        (plan §2 Step 6 / Step 5b).
        """
        return await self._dispatch_core(DelegationDispatchRequest(**request))

    async def _dispatch_core(
        self, validated: DelegationDispatchRequest
    ) -> dict[str, Any]:
        """Shared dispatch body: invoke the worker, estimate cost, capture eval.

        Returns the normalized handoff payload. Raises on any worker/LLM error
        (the caller — sync shim or worker node — decides how to surface it).
        """
        started_at = time.time()
        response = await self._invoke_worker(validated)
        content = str(getattr(response, "content", "") or "")
        usage = getattr(response, "usage_metadata", {}) or {}
        tokens_in = int(usage.get("input_tokens", 0) or 0)
        tokens_out = int(usage.get("output_tokens", 0) or 0)
        cost_usd = self._estimate_cost(tokens_in=tokens_in, tokens_out=tokens_out)
        latency_ms = (time.time() - started_at) * 1000
        await self._record_eval_capture(
            validated=validated,
            output_text=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        return {
            "status": "completed",
            "output": content,
            "error": None,
            "child_correlation_id": f"{validated.correlation_id}:child:{uuid.uuid4().hex[:8]}",
            # Governance Recording pillar: the worker LLM call's tokens/cost must
            # reach the STEP_EXECUTED carrier (eval_capture is a separate sink).
            # The worker node reads this to emit one STEP_EXECUTED per branch.
            "usage": {
                "model": self._worker_model_name,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
            },
        }

    def _run_async(self, coro: Any) -> Any:
        result = _ThreadResult()

        def _runner() -> None:
            try:
                result.value = asyncio.run(coro)
            except BaseException as exc:  # pragma: no cover - hard failure path
                result.error = exc

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        if result.error is not None:
            raise result.error
        return result.value

    async def _invoke_worker(self, validated: DelegationDispatchRequest) -> Any:
        profile = self._resolve_worker_profile()
        system_prompt = self._prompt_service.render_prompt(
            "subagents/delegation_worker_system_prompt",
            subagent_type=validated.subagent_type,
            constraints=validated.constraints,
            expected_output_schema=json.dumps(validated.expected_output_schema, sort_keys=True, indent=2),
        )
        return await self._llm_service.invoke(
            profile,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": validated.objective},
            ],
        )

    def _resolve_worker_profile(self):
        try:
            return self._llm_service.get_profile(self._worker_model_name)
        except KeyError:
            return default_fast_profile()

    def _estimate_cost(self, *, tokens_in: int, tokens_out: int) -> float:
        profile = self._resolve_worker_profile()
        return (
            tokens_in * profile.cost_per_1k_input / 1000.0
            + tokens_out * profile.cost_per_1k_output / 1000.0
        )

    async def _record_eval_capture(
        self,
        *,
        validated: DelegationDispatchRequest,
        output_text: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        latency_ms: float,
    ) -> None:
        from services import eval_capture

        await eval_capture.record(
            target="delegation_worker",
            ai_input={
                "subagent_type": validated.subagent_type,
                "objective": validated.objective,
                "constraints": validated.constraints,
                "correlation_id": validated.correlation_id,
            },
            ai_response=output_text[:5000],
            config={
                "configurable": {
                    "task_id": validated.task_id,
                    "user_id": validated.user_id,
                }
            },
            model=self._worker_model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
